from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

#from src.utils.config import ensure_run_dirs, get_all_article_ids, get_article_structure
from src.utils.config import (
    ensure_run_dirs,
    get_run_article_ids,
    get_article_structure,
)
from src.utils.io import load_json, save_json, write_manifest
from src.utils.logging import setup_logging
from src.validation.code_repository_validator import CodeRepositoryValidator
from src.validation.dataset_url_validator import DatasetURLValidator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)
    setup_logging(args.log_path or dirs["logs_dir"] / "url_validation.log")
    github_token = os.getenv("GITHUB_TOKEN")
    validators = [
        ("dataset", DatasetURLValidator(github_token), "dataset_result_path", "dataset_url_validation.json"),
        ("code_repository", CodeRepositoryValidator(github_token), "code_repository_result_path", "code_repository_validation.json"),
    ]
    #article_ids = get_all_article_ids()
    article_ids = get_run_article_ids(args.run_name)
    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]
    rows = []
    for article_id in article_ids:
        structure = get_article_structure(article_id)
        validation_dir = structure["validation_dir"]
        for kind, validator, source_key, out_name in validators:
            source_path = structure[source_key]
            out_path = validation_dir / out_name
            started = datetime.now().isoformat()
            status = "unknown"
            validated_count = 0
            error = ""
            if out_path.exists() and not args.overwrite:
                status = "skipped_existing"
            elif not source_path.exists():
                status = "missing_source"
            else:
                result = validator.run(article_id, load_json(source_path))
                save_json(result, out_path)
                status = result.get("status", "unknown")
                validated_count = result.get("validated_count", 0)
                error = result.get("error", {}).get("message", "") if status != "success" else ""
            rows.append({"article_id": article_id, "validator": validator.validator_name, "kind": kind, "status": status, "validated_count": validated_count, "source_path": str(source_path), "output_path": str(out_path), "error": error, "started_at": started, "finished_at": datetime.now().isoformat()})
            logging.info("%s %s: %s", article_id, kind, status)
    out_manifest = args.manifest or dirs["manifests_dir"] / "url_validation_manifest.csv"
    write_manifest(rows, out_manifest)
    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
