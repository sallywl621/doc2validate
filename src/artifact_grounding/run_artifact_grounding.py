from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.artifact_grounding.artifact_grounding_extractor import (
    ArtifactGroundingExtractor,
)
from src.utils.config import ensure_run_dirs, get_article_structure
from src.utils.io import save_json, write_manifest
from src.utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--run-name", required=True)
    parser.add_argument("--article-id", type=str, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)

    setup_logging(
        args.log_path
        or dirs["logs_dir"] / "artifact_grounding.log"
    )

    extractor = ArtifactGroundingExtractor()

    article_id = args.article_id

    output_dir = (
        dirs["run_dir"]
        / "artifact_grounding"
        / article_id
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "grounding_manifest.json"

    rows = []

    started = datetime.now().isoformat()
    status = "unknown"
    error = ""

    if output_path.exists() and not args.overwrite:
        status = "skipped_existing"

    else:
        try:
            logging.info(
                "Running artifact grounding: %s",
                article_id,
            )

            result = extractor.extract(
                article_id=article_id,
            )

            save_json(
                result,
                output_path,
            )

            status = result.get("status", "unknown")

            if status != "success":
                error = str(result.get("error", ""))

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

    out_manifest = (
        args.manifest
        or dirs["manifests_dir"] / "artifact_grounding_manifest.csv"
    )

    write_manifest(
        rows,
        out_manifest,
    )

    logging.info(
        "Manifest written: %s",
        out_manifest,
    )


if __name__ == "__main__":
    main()
