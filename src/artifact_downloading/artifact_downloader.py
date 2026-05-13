from __future__ import annotations

import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import requests

from src.artifact_downloading.base_downloader import BaseDownloader
from src.artifact_downloading.utils import (
    github_archive_urls,
    is_compressed_archive,
    is_data_file,
    is_direct_artifact_url,
    is_github_url,
    is_zenodo_url,
    normalize_url,
    parse_github_url,
    safe_name_from_url,
    should_skip_path,
)


class ArtifactDownloader(BaseDownloader):
    """
    Download validation-relevant dataset artifacts.

    The goal is NOT software reproduction.
    The goal is obtaining dataset artifacts usable later by
    generated validation code.
    """

    ZENODO_API = "https://zenodo.org/api/records"

    def download(
        self,
        article_id: str,
        urls: List[str],
        output_dir: Path,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        urls = list(dict.fromkeys(normalize_url(u) for u in urls if u))

        manifest: Dict[str, Any] = {
            "article_id": article_id,
            "downloader": "artifact_downloader",
            "dry_run": dry_run,
            "resources": [],
        }

        if not urls:
            manifest["resources"].append(
                {
                    "status": "skipped",
                    "reason": "no_candidate_urls",
                }
            )
            self.write_manifest(output_dir, manifest)
            return manifest

        for url in urls:
            if is_zenodo_url(url):
                entry = self._handle_zenodo(url, output_dir, dry_run)
            elif is_github_url(url):
                entry = self._handle_github(url, output_dir, dry_run)
            elif is_direct_artifact_url(url):
                entry = self._handle_direct_file(url, output_dir, dry_run)
            else:
                entry = {
                    "url": url,
                    "handler": "generic",
                    "download_mode": "unsupported_landing_page",
                    "status": "skipped",
                    "reason": "unsupported_or_landing_page_only",
                }

            manifest["resources"].append(entry)
            time.sleep(0.5)

        self.write_manifest(output_dir, manifest)
        return manifest

    def _handle_direct_file(
        self,
        url: str,
        output_dir: Path,
        dry_run: bool,
    ) -> Dict[str, Any]:
        fname = Path(url.split("?")[0]).name or safe_name_from_url(url)
        dest = output_dir / "files" / fname

        entry = {
            "url": url,
            "handler": "direct_file",
            "download_mode": (
                "compressed_archive"
                if is_compressed_archive(url)
                else "direct_file"
            ),
            "path": str(dest),
        }

        if dry_run:
            entry["status"] = "dry_run"
            return entry

        result = self.safe_download(url, dest)
        entry.update(result)
        return entry

    def _handle_github(
        self,
        url: str,
        output_dir: Path,
        dry_run: bool,
    ) -> Dict[str, Any]:
        parsed = parse_github_url(url)

        entry: Dict[str, Any] = {
            "url": url,
            "handler": "github_handler",
            "download_mode": "github_archive_zip",
            "parsed_github": parsed,
            "archive_attempts": [],
            "artifact_files": [],
        }

        if not parsed.get("valid"):
            entry["status"] = "skipped"
            entry["reason"] = "invalid_github_url"
            return entry

        owner = parsed["owner"]
        repo = parsed["repo"]
        branch = parsed.get("branch")
        subpath = parsed.get("subpath")
        repo_url = parsed["repo_url"]

        repo_key = safe_name_from_url(repo_url)
        github_dir = output_dir / "github" / repo_key
        archive_dir = github_dir / "archive"
        extract_dir = github_dir / "extracted"
        archive_dir.mkdir(parents=True, exist_ok=True)

        entry.update(
            {
                "repo_url": repo_url,
                "repo_key": repo_key,
                "github_dir": str(github_dir),
                "archive_dir": str(archive_dir),
                "extract_dir": str(extract_dir),
                "branch": branch,
                "subpath": subpath,
            }
        )

        if dry_run:
            entry["status"] = "dry_run"
            return entry

        repo_root: Path | None = self._find_extracted_repo_root(extract_dir, repo)

        if repo_root is not None:
            entry["reuse_status"] = "reused_existing_extracted_archive"

        else:
            download_result = self._download_and_extract_github_zip(
                owner=owner,
                repo=repo,
                branch=branch,
                repo_url=repo_url,
                archive_dir=archive_dir,
                extract_dir=extract_dir,
            )

            entry["archive_attempts"] = download_result.get("attempts", [])
            entry["repo_precheck"] = download_result.get("repo_precheck")

            if download_result.get("status") == "downloaded":
                entry["download_mode"] = "github_archive_zip"
                entry["downloaded_branch"] = download_result.get("branch")
                entry["archive_path"] = download_result.get("archive_path")
                entry["bytes"] = download_result.get("bytes")
                repo_root = self._find_extracted_repo_root(extract_dir, repo)

            elif download_result.get("reason") == "repo_too_large_precheck":
                entry["status"] = "skipped"
                entry["reason"] = "repo_too_large_precheck"
                entry["bytes"] = download_result.get("bytes")
                entry["size_mb"] = download_result.get("size_mb")
                entry["max_repo_size_mb"] = download_result.get(
                    "max_repo_size_mb"
                )
                return entry

            else:
                entry["archive_fallback"] = "git_clone"
                entry["download_mode"] = "github_archive_zip_then_git_clone"

                clone_dir = github_dir / "git_clone"
                clone_result = self.safe_git_clone(repo_url, clone_dir)

                entry["clone_status"] = clone_result.get("status")
                entry["clone_result"] = clone_result

                if clone_result.get("status") not in {"cloned", "reused_existing"}:
                    entry["status"] = clone_result.get("status", "failed")
                    entry["reason"] = clone_result.get(
                        "reason",
                        "github_archive_and_clone_failed",
                    )
                    return entry

                repo_root = clone_dir

        if repo_root is None or not repo_root.exists():
            entry["status"] = "failed"
            entry["reason"] = "repo_root_not_found_after_download"
            return entry

        entry["repo_root"] = str(repo_root)

        scan_root = repo_root / subpath if subpath else repo_root

        if subpath and not scan_root.exists():
            entry["subpath_scan_status"] = "subpath_not_found"
            entry["subpath_scan_root"] = str(scan_root)
            entry["fallback_scan_root"] = str(repo_root)
            scan_root = repo_root
        else:
            entry["subpath_scan_status"] = (
                "used_subpath" if subpath else "not_applicable"
            )

        artifact_files = self._scan_data_files(scan_root)

        entry["scan_root"] = str(scan_root)
        entry["artifact_files"] = artifact_files
        entry["artifact_count"] = len(artifact_files)

        downloaded_files = [
            f for f in artifact_files
            if f.get("status", "downloaded") == "downloaded"
        ]
        oversized_files = [
            f for f in artifact_files
            if f.get("reason") == "file_too_large"
        ]

        entry["downloadable_artifact_count"] = len(downloaded_files)
        entry["oversized_artifact_count"] = len(oversized_files)

        if downloaded_files:
            entry["status"] = "downloaded"
            entry["reason"] = "github_repo_contains_data_artifacts"
        elif oversized_files:
            entry["status"] = "skipped"
            entry["reason"] = "artifacts_exist_but_exceed_file_size_limit"
        else:
            entry["status"] = "skipped"
            entry["reason"] = "no_data_artifacts_found_in_github_repo"

        return entry

    def _download_and_extract_github_zip(
        self,
        owner: str,
        repo: str,
        branch: str | None,
        repo_url: str,
        archive_dir: Path,
        extract_dir: Path,
    ) -> Dict[str, Any]:
        attempts: List[Dict[str, Any]] = []

        repo_precheck = self.github_repo_precheck(repo_url)

        if repo_precheck.get("status") == "too_large":
            return {
                "status": "skipped",
                "reason": "repo_too_large_precheck",
                "repo_url": repo_url,
                "bytes": repo_precheck.get("bytes"),
                "size_mb": repo_precheck.get("size_mb"),
                "max_repo_size_mb": self.max_repo_size_mb,
                "repo_precheck": repo_precheck,
                "attempts": attempts,
            }

        for candidate_branch, archive_url in github_archive_urls(owner, repo, branch):
            archive_path = archive_dir / f"{candidate_branch}.zip"

            attempt = {
                "branch": candidate_branch,
                "archive_url": archive_url,
                "archive_path": str(archive_path),
                "repo_precheck": repo_precheck,
            }

            result = self.safe_download(archive_url, archive_path)
            attempt.update(result)
            attempts.append(attempt)

            if result.get("status") != "downloaded":
                continue

            try:
                if extract_dir.exists():
                    shutil.rmtree(extract_dir, ignore_errors=True)

                extract_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(extract_dir)

                size_bytes = self.dir_size_bytes(extract_dir)
                max_bytes = self.max_repo_size_mb * 1024 * 1024

                if size_bytes > max_bytes:
                    shutil.rmtree(extract_dir, ignore_errors=True)

                    return {
                        "status": "skipped",
                        "reason": "repo_too_large",
                        "repo_url": repo_url,
                        "branch": candidate_branch,
                        "archive_url": archive_url,
                        "archive_path": str(archive_path),
                        "bytes": size_bytes,
                        "size_mb": size_bytes / 1024 / 1024,
                        "max_repo_size_mb": self.max_repo_size_mb,
                        "repo_precheck": repo_precheck,
                        "attempts": attempts,
                    }

                return {
                    "status": "downloaded",
                    "branch": candidate_branch,
                    "archive_url": archive_url,
                    "archive_path": str(archive_path),
                    "bytes": result.get("bytes"),
                    "repo_precheck": repo_precheck,
                    "attempts": attempts,
                }

            except Exception as exc:
                attempts[-1]["extract_status"] = "failed"
                attempts[-1]["extract_reason"] = str(exc)

                if extract_dir.exists():
                    shutil.rmtree(extract_dir, ignore_errors=True)

                continue

        return {
            "status": "failed",
            "reason": "all_github_archive_attempts_failed",
            "repo_precheck": repo_precheck,
            "attempts": attempts,
        }

    def _find_extracted_repo_root(
        self,
        extract_dir: Path,
        repo: str,
    ) -> Path | None:
        if not extract_dir.exists():
            return None

        candidates = [p for p in extract_dir.iterdir() if p.is_dir()]

        if not candidates:
            return None

        repo_lower = repo.lower()

        for p in candidates:
            if p.name.lower().startswith(repo_lower + "-"):
                return p

        if len(candidates) == 1:
            return candidates[0]

        return candidates[0]

    def _scan_data_files(self, scan_root: Path) -> List[Dict[str, Any]]:
        artifacts: List[Dict[str, Any]] = []

        if not scan_root.exists():
            return artifacts

        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue

            rel_path = path.relative_to(scan_root)

            if should_skip_path(rel_path):
                continue

            if not is_data_file(path):
                continue

            try:
                size = path.stat().st_size
            except OSError:
                continue

            file_record = {
                "path": str(path),
                "relative_path": str(rel_path),
                "bytes": size,
                "file_type": path.suffix.lower(),
            }

            if size > self.max_file_size_mb * 1024 * 1024:
                file_record.update(
                    {
                        "status": "skipped",
                        "reason": "file_too_large",
                        "max_file_size_mb": self.max_file_size_mb,
                    }
                )
            else:
                file_record["status"] = "downloaded"

            artifacts.append(file_record)

        return artifacts

    def _handle_zenodo(
        self,
        url: str,
        output_dir: Path,
        dry_run: bool,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "url": url,
            "handler": "zenodo_handler",
            "download_mode": "zenodo_files",
            "files": [],
        }

        record_id = self._extract_zenodo_record_id(url)

        if not record_id:
            entry["status"] = "skipped"
            entry["reason"] = "no_zenodo_record_id"
            return entry

        api_url = f"{self.ZENODO_API}/{record_id}"

        try:
            resp = requests.get(api_url, timeout=self.timeout)
            resp.raise_for_status()
            record = resp.json()

        except Exception as exc:
            entry["status"] = "failed"
            entry["reason"] = str(exc)
            return entry

        files = record.get("files", [])

        if not files:
            entry["status"] = "skipped"
            entry["reason"] = "no_files_in_zenodo_record"
            return entry

        zenodo_dir = output_dir / "zenodo" / record_id
        zenodo_dir.mkdir(parents=True, exist_ok=True)
        entry["zenodo_dir"] = str(zenodo_dir)

        downloaded = 0

        for f in files:
            fname = f.get("key")
            links = f.get("links", {})
            download_url = links.get("self")

            if not fname or not download_url:
                continue

            dest = zenodo_dir / fname

            file_entry = {
                "filename": fname,
                "url": download_url,
                "path": str(dest),
                "download_mode": (
                    "compressed_archive"
                    if is_compressed_archive(fname)
                    else "zenodo_file"
                ),
            }

            if dry_run:
                file_entry["status"] = "dry_run"
                entry["files"].append(file_entry)
                continue

            result = self.safe_download(download_url, dest)
            file_entry.update(result)

            if result.get("status") == "downloaded":
                downloaded += 1

            entry["files"].append(file_entry)

        if dry_run:
            entry["status"] = "dry_run"

        elif downloaded > 0:
            entry["status"] = "downloaded"
            entry["downloaded_file_count"] = downloaded

        else:
            entry["status"] = "failed"
            entry["reason"] = "no_files_downloaded"

        return entry

    def _extract_zenodo_record_id(self, url: str) -> str | None:
        patterns = [
            r"zenodo\.org/record/(\d+)",
            r"zenodo\.org/records/(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)

            if match:
                return match.group(1)

        return None
