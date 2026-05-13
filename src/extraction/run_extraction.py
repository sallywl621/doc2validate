from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Type

from src.extraction.base_extractor import BaseExtractor
from src.extraction.code_repository_extractor import CodeRepositoryExtractor
from src.extraction.dataset_extractor import DatasetExtractor
#from src.utils.config import ensure_run_dirs, get_all_article_ids, get_article_structure
from src.utils.config import (
    ensure_run_dirs,
    get_run_article_ids,
    get_article_structure,
)
from src.utils.io import save_json, write_manifest
from src.utils.logging import setup_logging

EXTRACTORS: dict[str, Type[BaseExtractor]] = {
    "dataset": DatasetExtractor,
    "code_repository": CodeRepositoryExtractor,
}


def run_extractor(extractor_name: str, run_name: str, manifest_path: Path | None, log_path: Path | None, max_articles: int | None, overwrite: bool) -> None:
    dirs = ensure_run_dirs(run_name)
    setup_logging(log_path or dirs["logs_dir"] / f"{extractor_name}_extraction.log")
    extractor = EXTRACTORS[extractor_name]()
    #article_ids = get_all_article_ids()
    article_ids = get_run_article_ids(run_name)
    if max_articles is not None:
        article_ids = article_ids[:max_articles]
    rows = []
    logging.info("Start %s extraction: %d articles", extractor_name, len(article_ids))
    for idx, article_id in enumerate(article_ids, start=1):
        structure = get_article_structure(article_id)
        output_path = structure["dataset_result_path"] if extractor_name == "dataset" else structure["code_repository_result_path"]
        status = "unknown"
        error = ""
        started = datetime.now().isoformat()
        logging.info("[%d/%d] %s", idx, len(article_ids), article_id)
        if output_path.exists() and not overwrite:
            status = "skipped_existing"
        else:
            result = extractor.extract(article_id)
            save_json(result, output_path)
            status = result.get("status", "unknown")
            if status != "success":
                error = result.get("error", {}).get("message", "")
        rows.append({
            "article_id": article_id,
            "extractor": extractor_name,
            "status": status,
            "output_path": str(output_path),
            "error": error,
            "started_at": started,
            "finished_at": datetime.now().isoformat(),
        })
    out_manifest = manifest_path or dirs["manifests_dir"] / f"{extractor_name}_extraction_manifest.csv"
    write_manifest(rows, out_manifest)
    logging.info("Manifest written: %s", out_manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", choices=sorted(EXTRACTORS), required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_extractor(args.extractor, args.run_name, args.manifest, args.log_path, args.max_articles, args.overwrite)


if __name__ == "__main__":
    main()
