from __future__ import annotations


import argparse
from datetime import datetime
from pathlib import Path

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    list_effective_artifact_files,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--benchmark-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--max-articles",
        type=int,
    )

    parser.add_argument(
        "--article-id",
        type=str,
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
        or benchmark_root / "selected50_workspace_check.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        max_articles=args.max_articles,
        article_id=args.article_id,
    )

    rows = []

    for case in cases:
        started = datetime.now().isoformat()

        artifact_files = list_effective_artifact_files(case)

        rows.append(
            {
                "article_id": case.article_id,
                "case_dir_exists": case.case_dir.exists(),
                "json_dir_exists": case.json_dir.exists(),
                "dataset_json_exists": case.dataset_json_path.exists(),
                "structured_data_exists": case.structured_data_path.exists(),
                "scraped_repository_exists": case.scraped_repository_path.exists(),
                "dataset_structure_exists": case.dataset_structure_path.exists(),
                "legacy_dataset_structure_exists": case.legacy_dataset_structure_path.exists(),
                "pdf_dir_exists": case.pdf_dir.exists(),
                "artifact_dir_exists": case.artifact_dir.exists(),
                "effective_artifact_source": case.effective_artifact_source,
                "effective_artifact_root": str(case.effective_artifact_root),
                "effective_artifact_root_exists": case.effective_artifact_root.exists(),
                "num_effective_artifact_files": len(artifact_files),
                "num_effective_tabular_candidates": sum(
                    1 for f in artifact_files
                    if f.get("is_tabular_candidate")
                ),
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            }
        )

    if args.manifest:
        out_manifest = args.manifest
    elif args.article_id:
        out_manifest = benchmark_root / f"selected50_workspace_check_{args.article_id}.csv"
    else:
        out_manifest = benchmark_root / "selected50_workspace_check.csv"
        write_manifest(rows, out_manifest)

    print(f"Wrote workspace check manifest: {out_manifest}")


if __name__ == "__main__":
    main()
