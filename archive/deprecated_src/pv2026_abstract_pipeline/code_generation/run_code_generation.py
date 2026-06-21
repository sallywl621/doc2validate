from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.code_generation.code_generator import CodeGenerator
#from src.utils.config import DATA_DIR, ensure_run_dirs, get_all_article_ids, get_article_structure
from src.utils.config import (
    DATA_DIR,
    ensure_run_dirs,
    get_run_article_ids,
    get_article_structure,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--article-id", type=str)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)

    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)
    setup_logging(args.log_path or dirs["logs_dir"] / "code_generation.log")

    generator = CodeGenerator(top_k=args.top_k)

    if args.article_id:
        article_ids = [args.article_id]
    else:
        #article_ids = get_all_article_ids()
        article_ids = get_run_article_ids(args.run_name)

    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    generated_root = dirs["run_dir"] / "generated_code"
    generated_root.mkdir(parents=True, exist_ok=True)

    rows = []

    for article_id in article_ids:
        structure = get_article_structure(article_id)

        dataset_structure_path = structure["article_dir"] / "dataset_structure.json"
        artifact_root = DATA_DIR / "downloaded_artifacts" / article_id
        output_dir = generated_root / article_id
        generated_manifest_path = output_dir / "generated_manifest.json"

        started = datetime.now().isoformat()
        status = "unknown"
        error = ""
        failure_category = ""
        warning_count = 0
        selected_file_count = 0

        if generated_manifest_path.exists() and not args.overwrite:
            status = "skipped_existing"

        else:
            try:
                logging.info("Generating validation scaffold: %s", article_id)

                result = generator.generate(
                    article_id=article_id,
                    dataset_structure_path=dataset_structure_path,
                    artifact_root=artifact_root,
                    output_dir=output_dir,
                )

                failure = result.get("generation_failure")
                warnings = result.get("generation_warnings", [])
                selected = result.get("selected_primary_files", [])

                warning_count = len(warnings) if isinstance(warnings, list) else 0
                selected_file_count = len(selected) if isinstance(selected, list) else 0

                if failure:
                    status = "generation_failed"
                    failure_category = failure.get("category", "")
                    error = failure.get("detail", "")
                else:
                    status = "success"

            except Exception as exc:  # noqa: BLE001
                status = "error"
                error = str(exc)

        rows.append(
            {
                "article_id": article_id,
                "status": status,
                "failure_category": failure_category,
                "selected_file_count": selected_file_count,
                "warning_count": warning_count,
                "dataset_structure_path": str(dataset_structure_path),
                "artifact_root": str(artifact_root),
                "output_dir": str(output_dir),
                "error": error,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

        logging.info("%s: %s", article_id, status)

    out_manifest = args.manifest or dirs["manifests_dir"] / "code_generation_manifest.csv"
    write_manifest(rows, out_manifest)
    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
