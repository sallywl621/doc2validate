from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import requests


class BaseDownloader:
    """
    Base downloader for validation-relevant dataset artifacts.
    """

    def __init__(
        self,
        timeout: int = 60,
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

    def safe_git_clone(self, repo_url: str, dest_dir: Path) -> Dict[str, Any]:
        if dest_dir.exists():
            return {
                "status": "reused_existing",
                "path": str(dest_dir),
            }

        dest_dir.parent.mkdir(parents=True, exist_ok=True)

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
                    "path": str(dest_dir),
                }

            return {
                "status": "cloned",
                "bytes": size_bytes,
                "path": str(dest_dir),
            }

        except Exception as exc:
            shutil.rmtree(dest_dir, ignore_errors=True)

            return {
                "status": "failed",
                "reason": str(exc),
                "path": str(dest_dir),
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
