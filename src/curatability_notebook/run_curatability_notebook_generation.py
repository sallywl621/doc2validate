import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.curatability_notebook.notebook_builder import (
    CuratabilityNotebookBuilder,
    write_notebook,
)
from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    read_json_if_exists,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def manifest_row_from_notebook(
    article_id: str,
    output_path: Path,
    grounding: Dict[str, Any],
    status: str,
    error: str = "",
) -> Dict[str, Any]:
    summary = grounding.get("summary", {}) if isinstance(grounding, dict) else {}

    return {
        "article_id": article_id,
        "status": status,
        "error": error,
        "notebook_path": str(output_path),

        "num_logical_files": summary.get("num_logical_files"),
        "num_file_grounding_applicable": summary.get("num_file_grounding_applicable"),
        "num_resolved": summary.get("num_resolved"),
        "num_ambiguous": summary.get("num_ambiguous"),
        "num_weak_match": summary.get("num_weak_match"),
        "num_missing": summary.get("num_missing"),
        "num_unsupported_non_file_claim": summary.get("num_unsupported_non_file_claim"),
        "num_human_review_needed": summary.get("num_human_review_needed"),
        "grounding_score": summary.get("grounding_score"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--benchmark-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--article-id",
        type=str,
    )

    parser.add_argument(
        "--max-articles",
        type=int,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
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
        or benchmark_root / "curatability_notebook_generation.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    builder = CuratabilityNotebookBuilder()
    rows: List[Dict[str, Any]] = []

    for case in cases:
        started_at = datetime.now().isoformat()

        output_path = case.notebooks_dir / "curatability_review.ipynb"

        if output_path.exists() and not args.overwrite:
            row = manifest_row_from_notebook(
                article_id=case.article_id,
                output_path=output_path,
                grounding={},
                status="skipped_exists",
            )
            row["started_at"] = started_at
            row["finished_at"] = datetime.now().isoformat()
            rows.append(row)
            continue

        try:
            grounding = read_json_if_exists(case.refined_grounding_path)

            if not grounding:
                raise FileNotFoundError(
                    f"Missing refined grounding JSON: {case.refined_grounding_path}"
                )

            if grounding.get("_read_error"):
                raise ValueError(
                    f"Could not read grounding JSON: {grounding.get('_read_error')}"
                )

            notebook = builder.build(
                article_id=case.article_id,
                logical_schema_path=case.dataset_structure_path,
                grounding_path=case.refined_grounding_path,
                human_annotations_path=case.human_annotations_path,
                notebook_execution_path=case.notebook_execution_path,
                grounding=grounding,
            )

            write_notebook(notebook, output_path)

            row = manifest_row_from_notebook(
                article_id=case.article_id,
                output_path=output_path,
                grounding=grounding,
                status="success",
            )

        except Exception as exc:
            row = manifest_row_from_notebook(
                article_id=case.article_id,
                output_path=output_path,
                grounding={},
                status="error",
                error=str(exc),
            )

        row["started_at"] = started_at
        row["finished_at"] = datetime.now().isoformat()
        rows.append(row)

    if args.manifest:
        out_manifest = args.manifest
    elif args.article_id:
        out_manifest = (
            benchmark_root
            / f"curatability_notebook_generation_manifest_{args.article_id}.csv"
        )
    else:
        out_manifest = benchmark_root / "curatability_notebook_generation_manifest.csv"

    write_manifest(rows, out_manifest)

    print(f"Wrote notebook generation manifest: {out_manifest}")

    ok_rows = [
        r for r in rows
        if r.get("status") == "success"
    ]

    print("\nSummary")
    print("-------")
    print("n cases:", len(rows))
    print("success:", len(ok_rows))
    print(
        "human_review_needed:",
        sum(int(r.get("num_human_review_needed") or 0) for r in ok_rows),
    )

    if ok_rows:
        avg_grounding_score = sum(
            float(r.get("grounding_score") or 0.0)
            for r in ok_rows
        ) / len(ok_rows)

        print("avg grounding_score:", round(avg_grounding_score, 4))


if __name__ == "__main__":
    main()
