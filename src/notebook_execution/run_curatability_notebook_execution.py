import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import time

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    read_json_if_exists,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def execute_notebook_with_nbclient(
    notebook_path: Path,
    timeout: int,
    kernel_name: str,
    allow_errors: bool,
) -> None:
    """
    Execute a notebook in place using nbclient.

    This avoids jupyter nbconvert, which can fail in this environment because
    jupyter_contrib_nbextensions expects notebook.services from older notebook
    versions.
    """
    import nbformat
    from nbclient import NotebookClient

    nb = nbformat.read(notebook_path, as_version=4)

    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name=kernel_name,
        allow_errors=allow_errors,
    )

    client.execute()

    nbformat.write(nb, notebook_path)


def count_annotations(annotation_obj: Dict[str, Any]) -> Dict[str, int]:
    annotations = annotation_obj.get("annotations") or []

    total = len(annotations)

    empty_annotation_type = sum(
        1 for a in annotations
        if not str(a.get("annotation_type", "") or "").strip()
    )

    final_decisions = sum(
        1 for a in annotations
        if a.get("annotation_scope") == "final_decision"
    )

    grounding_annotations = sum(
        1 for a in annotations
        if a.get("annotation_scope") == "grounding"
    )

    return {
        "num_annotations": total,
        "num_grounding_annotations": grounding_annotations,
        "num_final_decision_annotations": final_decisions,
        "num_empty_annotation_type": empty_annotation_type,
    }


def manifest_row(
    article_id: str,
    notebook_path: Path,
    notebook_execution_path: Path,
    human_annotations_path: Path,
    status: str,
    error: str = "",
    elapsed_seconds: float | None = None,
) -> Dict[str, Any]:
    execution_obj = read_json_if_exists(notebook_execution_path)
    annotation_obj = read_json_if_exists(human_annotations_path)

    grounding_summary = execution_obj.get("grounding_summary", {}) if execution_obj else {}

    annotation_counts = (
        count_annotations(annotation_obj)
        if annotation_obj and not annotation_obj.get("_read_error")
        else {
            "num_annotations": None,
            "num_grounding_annotations": None,
            "num_final_decision_annotations": None,
            "num_empty_annotation_type": None,
        }
    )

    return {
        "article_id": article_id,
        "status": status,
        "error": error,

        "notebook_path": str(notebook_path),
        "notebook_execution_path": str(notebook_execution_path),
        "human_annotations_path": str(human_annotations_path),

        "elapsed_seconds": elapsed_seconds,

        "notebook_execution_exists": notebook_execution_path.exists(),
        "human_annotations_exists": human_annotations_path.exists(),

        "grounding_score": grounding_summary.get("grounding_score"),
        "num_logical_files": grounding_summary.get("num_logical_files"),
        "num_file_grounding_applicable": grounding_summary.get("num_file_grounding_applicable"),
        "num_resolved": grounding_summary.get("num_resolved"),
        "num_ambiguous": grounding_summary.get("num_ambiguous"),
        "num_weak_match": grounding_summary.get("num_weak_match"),
        "num_missing": grounding_summary.get("num_missing"),
        "num_unsupported_non_file_claim": grounding_summary.get("num_unsupported_non_file_claim"),
        "num_human_review_needed": grounding_summary.get("num_human_review_needed"),

        "num_preview_results": execution_obj.get("num_preview_results") if execution_obj else None,
        "num_preview_success": execution_obj.get("num_preview_success") if execution_obj else None,
        "num_preview_failed": execution_obj.get("num_preview_failed") if execution_obj else None,

        **annotation_counts,
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
        help=(
            "Re-execute even if notebook_execution.json and "
            "human_annotations.json already exist."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
    )

    parser.add_argument(
        "--kernel-name",
        type=str,
        default="python3",
    )

    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help=(
            "Allow notebook cells to error and continue execution. "
            "Use this only when collecting failure evidence intentionally."
        ),
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
        or benchmark_root / "curatability_notebook_execution.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    rows: List[Dict[str, Any]] = []

    for case in cases:
        started_at = datetime.now().isoformat()

        notebook_path = case.notebooks_dir / "curatability_review.ipynb"
        notebook_execution_path = case.notebook_execution_path
        human_annotations_path = case.human_annotations_path

        if not notebook_path.exists():
            row = manifest_row(
                article_id=case.article_id,
                notebook_path=notebook_path,
                notebook_execution_path=notebook_execution_path,
                human_annotations_path=human_annotations_path,
                status="missing_notebook",
                error=f"Missing notebook: {notebook_path}",
            )
            row["started_at"] = started_at
            row["finished_at"] = datetime.now().isoformat()
            rows.append(row)
            continue

        outputs_exist = (
            notebook_execution_path.exists()
            and human_annotations_path.exists()
        )

        if outputs_exist and not args.overwrite:
            row = manifest_row(
                article_id=case.article_id,
                notebook_path=notebook_path,
                notebook_execution_path=notebook_execution_path,
                human_annotations_path=human_annotations_path,
                status="skipped_exists",
            )
            row["started_at"] = started_at
            row["finished_at"] = datetime.now().isoformat()
            rows.append(row)
            continue

        t0 = time.time()

        try:
            execute_notebook_with_nbclient(
                notebook_path=notebook_path,
                timeout=args.timeout,
                kernel_name=args.kernel_name,
                allow_errors=args.allow_errors,
            )

            elapsed = round(time.time() - t0, 4)

            row = manifest_row(
                article_id=case.article_id,
                notebook_path=notebook_path,
                notebook_execution_path=notebook_execution_path,
                human_annotations_path=human_annotations_path,
                status="success",
                elapsed_seconds=elapsed,
            )

        except Exception as exc:
            elapsed = round(time.time() - t0, 4)

            row = manifest_row(
                article_id=case.article_id,
                notebook_path=notebook_path,
                notebook_execution_path=notebook_execution_path,
                human_annotations_path=human_annotations_path,
                status="error",
                error=str(exc),
                elapsed_seconds=elapsed,
            )

        row["started_at"] = started_at
        row["finished_at"] = datetime.now().isoformat()

        rows.append(row)

    if args.manifest:
        out_manifest = args.manifest
    elif args.article_id:
        out_manifest = (
            benchmark_root
            / f"curatability_notebook_execution_manifest_{args.article_id}.csv"
        )
    else:
        out_manifest = benchmark_root / "curatability_notebook_execution_manifest.csv"

    write_manifest(rows, out_manifest)

    print(f"Wrote notebook execution manifest: {out_manifest}")

    ok_rows = [
        r for r in rows
        if r.get("status") == "success"
    ]

    print("\nSummary")
    print("-------")
    print("n cases:", len(rows))
    print("success:", len(ok_rows))
    print("errors:", sum(1 for r in rows if r.get("status") == "error"))
    print("skipped_exists:", sum(1 for r in rows if r.get("status") == "skipped_exists"))
    print(
        "preview_success:",
        sum(int(r.get("num_preview_success") or 0) for r in ok_rows),
    )
    print(
        "preview_failed:",
        sum(int(r.get("num_preview_failed") or 0) for r in ok_rows),
    )
    print(
        "annotations:",
        sum(int(r.get("num_annotations") or 0) for r in ok_rows),
    )


if __name__ == "__main__":
    main()
