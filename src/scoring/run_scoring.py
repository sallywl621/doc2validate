from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from src.scoring.feature_extractor import extract_features_for_article
from src.scoring.scs import compute_scs_from_features
from src.utils.config import (
    RESULTS_DIR,
    ensure_run_dirs,
    get_article_structure,
    get_run_article_ids,
)
from src.utils.io import save_json, write_manifest
from src.utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)

    setup_logging(
        args.log_path
        or dirs["logs_dir"] / "scoring.log"
    )

    article_ids = get_run_article_ids(args.run_name)

    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    rows = []

    for article_id in article_ids:
        started = datetime.now().isoformat()
        status = "unknown"
        error = ""

        structure = get_article_structure(article_id)

        output_path = structure["article_dir"] / "scs.json"

        generated_manifest_path = (
            RESULTS_DIR
            / "runs"
            / args.run_name
            / "generated_code"
            / article_id
            / "generated_manifest.json"
        )

        if output_path.exists() and not args.overwrite:
            status = "skipped_existing"
            scs_value = ""
            scs_norm = ""

        else:
            try:
                features = extract_features_for_article(
                    article_id=article_id,
                    dataset_structure_path=(
                        structure["article_dir"]
                        / "dataset_structure.json"
                    ),
                    scraped_repository_path=structure["scraped_repository_path"],
                    validation_dir=structure["validation_dir"],
                    generated_manifest_path=generated_manifest_path,
                )

                if not features:
                    status = "error"
                    error = "feature_extraction_failed"
                    scs_value = ""
                    scs_norm = ""

                else:
                    score = compute_scs_from_features(features)

                    payload = {
                        "article_id": article_id,
                        "scoring_status": "success",
                        "features": features,
                        **score,
                    }

                    save_json(payload, output_path)

                    status = "success"
                    scs_value = score["scs"]
                    scs_norm = score["scs_normalized"]

            except Exception as exc:
                status = "error"
                error = str(exc)
                scs_value = ""
                scs_norm = ""

        rows.append(
            {
                "article_id": article_id,
                "status": status,
                "scs": scs_value,
                "scs_normalized": scs_norm,
                "output_path": str(output_path),
                "error": error,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

        logging.info("%s: %s", article_id, status)

    out_manifest = (
        args.manifest
        or dirs["manifests_dir"] / "scoring_manifest.csv"
    )

    write_manifest(rows, out_manifest)

    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
