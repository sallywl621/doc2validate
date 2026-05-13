from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.artifact_downloading.artifact_downloader import ArtifactDownloader
from src.utils.config import (
    ensure_run_dirs,
    get_run_article_ids,
    get_article_structure,
)
from src.utils.io import load_json, write_manifest
from src.utils.logging import setup_logging


def collect_dataset_urls(validation_dir: Path) -> List[str]:
    """
    Collect dataset artifact URLs from dataset URL validation results only.

    Important experimental boundary:
    - This downloader uses dataset URLs only.
    - It does not use code_repository.json.
    - It does not use scraped_repository.json as an additional fallback.
    """
    path = validation_dir / "dataset_url_validation.json"

    if not path.exists():
        return []

    data = load_json(path)

    urls: List[str] = []

    for item in data.get("results", []):
        if item.get("accessible") is True:
            url = item.get("redirected_url") or item.get("url")
            if url:
                urls.append(url)

    return sorted(set(urls))


def manifest_has_downloaded_resource(manifest_path: Path) -> bool:
    """
    Return True only when an existing article-level artifact manifest
    contains at least one downloaded resource.

    This allows automatic reruns for manifests that contain only skipped,
    failed, or no-artifact results.
    """
    if not manifest_path.exists():
        return False

    try:
        data: Dict[str, Any] = load_json(manifest_path)
    except Exception:
        return False

    for resource in data.get("resources", []):
        if resource.get("status") == "downloaded":
            return True

        for f in resource.get("files", []):
            if f.get("status") == "downloaded":
                return True

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download dataset artifacts for execution validation. "
            "This script intentionally uses dataset URLs only."
        )
    )

    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)

    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-file-size-mb", type=int, default=500)
    parser.add_argument("--max-repo-size-mb", type=int, default=1000)

    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)

    setup_logging(
        args.log_path
        or dirs["logs_dir"] / "artifact_downloader.log"
    )

    downloader = ArtifactDownloader(
        timeout=args.timeout,
        max_file_size_mb=args.max_file_size_mb,
        max_repo_size_mb=args.max_repo_size_mb,
    )

    article_ids = get_run_article_ids(args.run_name)

    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    rows = []

    for article_id in article_ids:
        structure = get_article_structure(article_id)
        output_dir = structure["downloaded_artifacts_dir"]
        manifest_path = output_dir / "ARTIFACT_DOWNLOAD_MANIFEST.json"

        started = datetime.now().isoformat()
        status = "unknown"
        error = ""
        candidate_urls: List[str] = []

        if (
            manifest_has_downloaded_resource(manifest_path)
            and not args.overwrite
        ):
            status = "skipped_existing_success"

        else:
            candidate_urls = collect_dataset_urls(
                structure["validation_dir"]
            )

            if not candidate_urls:
                status = "no_dataset_candidate_urls"

            else:
                try:
                    result = downloader.download(
                        article_id=article_id,
                        urls=candidate_urls,
                        output_dir=output_dir,
                        dry_run=args.dry_run,
                    )

                    resources = result.get("resources", [])

                    downloaded_count = 0
                    for r in resources:
                        if r.get("status") == "downloaded":
                            downloaded_count += 1
                        downloaded_count += sum(
                            1
                            for f in r.get("files", [])
                            if f.get("status") == "downloaded"
                        )

                    if args.dry_run:
                        status = "dry_run"

                    elif downloaded_count > 0:
                        status = "success"

                    else:
                        status = "no_downloaded_artifacts"

                except Exception as exc:
                    status = "error"
                    error = str(exc)

        rows.append(
            {
                "article_id": article_id,
                "status": status,
                "candidate_url_count": len(candidate_urls),
                "candidate_urls": json.dumps(
                    candidate_urls,
                    ensure_ascii=False,
                ),
                "output_dir": str(output_dir),
                "error": error,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

        logging.info(
            "%s: %s (%d dataset candidate urls)",
            article_id,
            status,
            len(candidate_urls),
        )

    out_manifest = (
        args.manifest
        or dirs["manifests_dir"] / "artifact_download_manifest.csv"
    )

    write_manifest(rows, out_manifest)

    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
