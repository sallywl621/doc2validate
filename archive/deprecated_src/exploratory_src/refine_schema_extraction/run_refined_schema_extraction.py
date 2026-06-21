import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.refine_schema_extraction.refined_schema_extractor import (
    RefinedDatasetStructureExtractor,
)
from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    build_case_context,
    backup_legacy_dataset_structure,
)
from src.utils.io import save_json, write_manifest
from src.utils.logging import setup_logging


def get_result_status(result: Dict[str, Any]) -> tuple[str, str]:
    """
    Normalize BaseExtractor result status.
    """
    if result.get("status") == "success":
        return "success", ""

    message = ""

    if isinstance(result.get("result"), dict):
        message = str(result["result"].get("message", ""))

    if not message:
        message = str(result.get("message", ""))

    return "error", message


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--benchmark-root",
        type=Path,
        required=True,
        help="Path to scidata_selected_50_v1 benchmark workspace.",
    )

    parser.add_argument(
        "--article-id",
        type=str,
        help="Run one article only.",
    )

    parser.add_argument(
        "--max-articles",
        type=int,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite <article_id>/json/dataset_structure.json.",
    )

    parser.add_argument(
        "--backup-legacy",
        action="store_true",
        help=(
            "Backup existing dataset_structure.json to "
            "dataset_structure_legacy_run4293.json before overwrite."
        ),
    )

    parser.add_argument(
        "--overwrite-backup",
        action="store_true",
        help="Overwrite existing dataset_structure_legacy_run4293.json.",
    )

    parser.add_argument(
        "--manifest",
        type=Path,
    )

    parser.add_argument(
        "--log-path",
        type=Path,
    )

    args = parser.parse_args()

    benchmark_root = args.benchmark_root.resolve()

    setup_logging(
        args.log_path
        or benchmark_root / "refined_schema_extraction.log"
    )

    extractor = RefinedDatasetStructureExtractor()

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        max_articles=args.max_articles,
        article_id=args.article_id,
    )

    rows = []

    for case in cases:
        started = datetime.now().isoformat()

        output_path = case.dataset_structure_path
        metadata_path = case.json_dir / "dataset_structure_refinement_metadata.json"

        status = "unknown"
        error = ""
        backup_created = False

        if output_path.exists() and not args.overwrite:
            status = "skipped_existing"

        else:
            try:
                logging.info(
                    "Refining dataset structure: %s",
                    case.article_id,
                )

                if args.backup_legacy:
                    backup_created = backup_legacy_dataset_structure(
                        case,
                        overwrite_backup=args.overwrite_backup,
                    )

                case_context = build_case_context(case)

                result = extractor.extract_from_case_context(
                    article_id=case.article_id,
                    case_context=case_context,
                )

                save_json(result, output_path)

                save_json(
                    {
                        "article_id": case.article_id,
                        "schema_version": "curatability_schema_v2",
                        "benchmark_root": str(benchmark_root),
                        "case_dir": str(case.case_dir),
                        "effective_artifact_source": case.effective_artifact_source,
                        "effective_artifact_root": str(case.effective_artifact_root),
                        "legacy_backup_path": str(case.legacy_dataset_structure_path),
                        "backup_created": backup_created,
                        "output_path": str(output_path),
                        "started_at": started,
                        "finished_at": datetime.now().isoformat(),
                    },
                    metadata_path,
                )

                status, error = get_result_status(result)

            except Exception as exc:
                status = "error"
                error = str(exc)

                logging.exception(
                    "Failed refining dataset structure: %s",
                    case.article_id,
                )

        rows.append(
            {
                "article_id": case.article_id,
                "status": status,
                "output_path": str(output_path),
                "metadata_path": str(metadata_path),
                "legacy_backup_path": str(case.legacy_dataset_structure_path),
                "backup_created": backup_created,
                "error": error,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

        logging.info(
            "%s: %s",
            case.article_id,
            status,
        )

    if args.manifest:
        out_manifest = args.manifest
    elif args.article_id:
        out_manifest = (
            benchmark_root
            / f"refined_schema_extraction_manifest_{args.article_id}.csv"
        )
    else:
        out_manifest = benchmark_root / "refined_schema_extraction_manifest.csv"

    write_manifest(rows, out_manifest)

    logging.info(
        "Manifest written: %s",
        out_manifest,
    )

    print(f"Wrote manifest: {out_manifest}")


if __name__ == "__main__":
    main()
