from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.utils.config import ensure_run_dirs, get_all_article_ids, get_article_structure
from src.utils.io import load_json, save_json, write_manifest
from src.utils.logging import setup_logging


def collect_accessible_urls(validation_dir: Path) -> List[str]:
    urls: List[str] = []
    for path in validation_dir.glob("*_validation.json"):
        try:
            data = load_json(path)
        except Exception:
            continue
        for item in data.get("results", []):
            if item.get("accessible") is True and item.get("redirected_url"):
                urls.append(item["redirected_url"])
    return sorted(set(urls))


def fallback_scrape(article_id: str, urls: List[str]) -> Dict[str, Any]:
    """Placeholder output. Replace this with your existing RepositoryExtractor integration."""
    return {
        "article_id": article_id,
        "source": "repository_crawler_placeholder",
        "repository_urls": urls,
        "chunks": [],
        "note": "Integrate existing RepositoryExtractor here.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)
    setup_logging(args.log_path or dirs["logs_dir"] / "repository_crawler.log")
    article_ids = get_all_article_ids()
    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    rows = []
    for article_id in article_ids:
        structure = get_article_structure(article_id)
        out_path = structure["scraped_repository_path"]
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
                # Later: import and call your real RepositoryExtractor here.
                result = fallback_scrape(article_id, urls)
                save_json(result, out_path)
                status = "success"
            except Exception as exc:  # noqa: BLE001
                status = "error"
                error = str(exc)
        rows.append({"article_id": article_id, "status": status, "url_count": len(urls), "urls": json.dumps(urls, ensure_ascii=False), "output_path": str(out_path), "error": error, "started_at": started, "finished_at": datetime.now().isoformat()})
        logging.info("%s: %s (%d urls)", article_id, status, len(urls))
    out_manifest = args.manifest or dirs["manifests_dir"] / "repository_crawl_manifest.csv"
    write_manifest(rows, out_manifest)
    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
