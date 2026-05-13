from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests


class BaseDownloader:
    """
    Base downloader for validation-relevant dataset artifacts.
    """

    def __init__(
        self,
        timeout: int = 5,
        max_file_size_mb: int = 500,
        max_repo_size_mb: int = 1000,
    ):
        self.timeout = timeout
        self.max_file_size_mb = max_file_size_mb
        self.max_repo_size_mb = max_repo_size_mb

    def safe_download(self, url: str, dest_path: Path) -> Dict[str, Any]:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        max_bytes = self.max_file_size_mb * 1024 * 1024
        total = 0

        try:
            with requests.get(url, stream=True, timeout=self.timeout) as resp:
                resp.raise_for_status()

                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue

                        total += len(chunk)

                        if total > max_bytes:
                            if dest_path.exists():
                                dest_path.unlink()

                            return {
                                "status": "skipped",
                                "reason": "file_too_large",
                                "bytes": total,
                                "max_bytes": max_bytes,
                                "path": str(dest_path),
                            }

                        f.write(chunk)

            return {
                "status": "downloaded",
                "bytes": total,
                "path": str(dest_path),
            }

        except Exception as exc:
            return {
                "status": "failed",
                "reason": str(exc),
                "path": str(dest_path),
            }

    def parse_github_owner_repo(
        self,
        repo_url: str,
    ) -> Optional[tuple[str, str]]:
        parsed = urlparse(repo_url.rstrip("/"))

        if "github.com" not in parsed.netloc.lower():
            return None

        parts = [p for p in parsed.path.split("/") if p]

        if len(parts) < 2:
            return None

        owner = parts[0]
        repo = parts[1].replace(".git", "")

        if not owner or not repo:
            return None

        return owner, repo

    def github_repo_precheck(self, repo_url: str) -> Dict[str, Any]:
        """
        Precheck GitHub repository size before archive download or clone.

        GitHub REST API field `size` is in KB.
        This is not perfect, but it is good enough to skip clearly oversized
        repositories before wasting time downloading archives.
        """
        parsed = self.parse_github_owner_repo(repo_url)

        if parsed is None:
            return {
                "status": "not_github",
                "repo_url": repo_url,
            }

        owner, repo = parsed
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        try:
            resp = requests.get(
                api_url,
                timeout=min(self.timeout, 30),
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "doc2validate-artifact-downloader",
                },
            )

            if resp.status_code != 200:
                return {
                    "status": "unknown",
                    "reason": f"github_api_status_{resp.status_code}",
                    "repo_url": repo_url,
                    "api_url": api_url,
                }

            data = resp.json()
            size_kb = data.get("size")
            default_branch = data.get("default_branch")

            if size_kb is None:
                return {
                    "status": "unknown",
                    "reason": "github_api_missing_size",
                    "repo_url": repo_url,
                    "api_url": api_url,
                    "default_branch": default_branch,
                }

            size_bytes = int(size_kb) * 1024
            size_mb = size_bytes / 1024 / 1024
            max_bytes = self.max_repo_size_mb * 1024 * 1024

            if size_bytes > max_bytes:
                return {
                    "status": "too_large",
                    "reason": "repo_too_large_precheck",
                    "bytes": size_bytes,
                    "size_kb": size_kb,
                    "size_mb": size_mb,
                    "max_bytes": max_bytes,
                    "max_repo_size_mb": self.max_repo_size_mb,
                    "repo_url": repo_url,
                    "api_url": api_url,
                    "default_branch": default_branch,
                }

            return {
                "status": "ok",
                "bytes": size_bytes,
                "size_kb": size_kb,
                "size_mb": size_mb,
                "max_bytes": max_bytes,
                "max_repo_size_mb": self.max_repo_size_mb,
                "repo_url": repo_url,
                "api_url": api_url,
                "default_branch": default_branch,
            }

        except Exception as exc:
            return {
                "status": "unknown",
                "reason": str(exc),
                "repo_url": repo_url,
                "api_url": api_url,
            }

    def safe_git_clone(self, repo_url: str, dest_dir: Path) -> Dict[str, Any]:
        if dest_dir.exists():
            return {
                "status": "reused_existing",
                "path": str(dest_dir),
            }

        dest_dir.parent.mkdir(parents=True, exist_ok=True)

        precheck = self.github_repo_precheck(repo_url)

        if precheck.get("status") == "too_large":
            return {
                "status": "skipped",
                "reason": "repo_too_large_precheck",
                "bytes": precheck.get("bytes"),
                "size_mb": precheck.get("size_mb"),
                "max_repo_size_mb": self.max_repo_size_mb,
                "path": str(dest_dir),
                "repo_url": repo_url,
                "precheck": precheck,
            }

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(dest_dir)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.timeout * 4,
            )

            size_bytes = self.dir_size_bytes(dest_dir)
            max_bytes = self.max_repo_size_mb * 1024 * 1024

            if size_bytes > max_bytes:
                shutil.rmtree(dest_dir, ignore_errors=True)

                return {
                    "status": "skipped",
                    "reason": "repo_too_large",
                    "bytes": size_bytes,
                    "max_bytes": max_bytes,
                    "max_repo_size_mb": self.max_repo_size_mb,
                    "path": str(dest_dir),
                    "repo_url": repo_url,
                    "precheck": precheck,
                }

            return {
                "status": "cloned",
                "bytes": size_bytes,
                "path": str(dest_dir),
                "repo_url": repo_url,
                "precheck": precheck,
            }

        except Exception as exc:
            shutil.rmtree(dest_dir, ignore_errors=True)

            return {
                "status": "failed",
                "reason": str(exc),
                "path": str(dest_dir),
                "repo_url": repo_url,
                "precheck": precheck,
            }

    def dir_size_bytes(self, path: Path) -> int:
        total = 0

        if not path.exists():
            return 0

        for root, _, files in os.walk(path):
            for fname in files:
                fpath = Path(root) / fname

                try:
                    total += fpath.stat().st_size
                except OSError:
                    pass

        return total

    def write_manifest(self, output_dir: Path, manifest: Dict[str, Any]) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest["generated_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        )

        path = output_dir / "ARTIFACT_DOWNLOAD_MANIFEST.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
