from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from src.repository_crawling.extractor import RepositoryExtractor
#from src.utils.config import ensure_run_dirs, get_all_article_ids, get_article_structure
from src.utils.config import (
    ensure_run_dirs,
    get_run_article_ids,
    get_article_structure,
)
from src.utils.io import load_json, write_manifest
from src.utils.logging import setup_logging


def collect_accessible_urls(validation_dir: Path) -> List[str]:
    """
    Collect accessible redirected URLs from all validation files.

    This includes both:
    - dataset_url_validation.json
    - code_repository_validation.json
    """
    urls: List[str] = []

    if not validation_dir.exists():
        return urls

    for path in validation_dir.glob("*_validation.json"):
        try:
            data = load_json(path)
        except Exception:
            continue

        for item in data.get("results", []):
            if item.get("accessible") is True and item.get("redirected_url"):
                urls.append(item["redirected_url"])

    return sorted(set(urls))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")

    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--max-pages-per-domain", type=int, default=20)

    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)
    setup_logging(args.log_path or dirs["logs_dir"] / "repository_crawler.log")

    crawler = RepositoryExtractor(
        max_depth=args.max_depth,
        chunk_size=args.chunk_size,
        max_pages_per_domain=args.max_pages_per_domain,
    )

    #article_ids = get_all_article_ids()
    article_ids = get_run_article_ids(args.run_name)

    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    rows = []

    for article_id in article_ids:
        structure = get_article_structure(article_id)
        out_path = structure["scraped_repository_path"]
        output_dir = out_path.parent

        started = datetime.now().isoformat()
        urls = collect_accessible_urls(structure["validation_dir"])

        status = "unknown"
        error = ""

        if out_path.exists() and not args.overwrite:
            status = "skipped_existing"

        elif not urls:
            status = "no_accessible_urls"

        else:
            try:
                crawler.extract(
                    article_id=article_id,
                    repository_urls=urls,
                    output_dir=output_dir,
                )
                status = "success"

            except Exception as exc:  # noqa: BLE001
                status = "error"
                error = str(exc)

        rows.append(
            {
                "article_id": article_id,
                "status": status,
                "url_count": len(urls),
                "urls": json.dumps(urls, ensure_ascii=False),
                "output_path": str(out_path),
                "error": error,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

        logging.info("%s: %s (%d urls)", article_id, status, len(urls))

    out_manifest = args.manifest or dirs["manifests_dir"] / "repository_crawl_manifest.csv"
    write_manifest(rows, out_manifest)

    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
