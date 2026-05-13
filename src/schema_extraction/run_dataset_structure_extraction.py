from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.schema_extraction.dataset_structure_extractor import (
    DatasetStructureExtractor,
)
from src.utils.config import (
    ensure_run_dirs,
    get_run_article_ids,
    get_article_structure,
)
from src.utils.io import save_json, write_manifest
from src.utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--run-name", required=True)

    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)

    parser.add_argument("--max-articles", type=int)

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    # --------------------------------------------------------------
    # Run directories
    # --------------------------------------------------------------

    dirs = ensure_run_dirs(args.run_name)

    setup_logging(
        args.log_path
        or dirs["logs_dir"] / "dataset_structure_extraction.log"
    )

    # --------------------------------------------------------------
    # Extractor
    # --------------------------------------------------------------

    extractor = DatasetStructureExtractor()

    # --------------------------------------------------------------
    # Article list
    # --------------------------------------------------------------

    #article_ids = get_all_article_ids()
    article_ids = get_run_article_ids(args.run_name)

    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    rows = []

    # --------------------------------------------------------------
    # Main loop
    # --------------------------------------------------------------

    for article_id in article_ids:
        structure = get_article_structure(article_id)

        output_path = (
            structure["article_dir"]
            / "dataset_structure.json"
        )

        started = datetime.now().isoformat()

        status = "unknown"
        error = ""

        # ----------------------------------------------------------
        # Skip existing
        # ----------------------------------------------------------

        if output_path.exists() and not args.overwrite:
            status = "skipped_existing"

        else:
            try:
                logging.info(
                    "Extracting dataset structure: %s",
                    article_id,
                )

                result = extractor.extract(article_id)

                save_json(result, output_path)

                if result.get("status") == "success":
                    status = "success"
                else:
                    status = "error"
                    error = (
                        result.get("result", {})
                        .get("message", "")
                    )

            except Exception as exc:
                status = "error"
                error = str(exc)

        rows.append(
            {
                "article_id": article_id,
                "status": status,
                "output_path": str(output_path),
                "error": error,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

        logging.info(
            "%s: %s",
            article_id,
            status,
        )

    # --------------------------------------------------------------
    # Write manifest
    # --------------------------------------------------------------

    out_manifest = (
        args.manifest
        or (
            dirs["manifests_dir"]
            / "dataset_structure_extraction_manifest.csv"
        )
    )

    write_manifest(rows, out_manifest)

    logging.info(
        "Manifest written: %s",
        out_manifest,
    )


if __name__ == "__main__":
    main()
