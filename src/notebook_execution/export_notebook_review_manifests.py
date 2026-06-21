import argparse
from pathlib import Path
from typing import Any, Dict, List

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    read_json_if_exists,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def article_row_from_outputs(
    article_id: str,
    notebook_execution_path: Path,
    human_annotations_path: Path,
) -> Dict[str, Any]:
    execution_obj = read_json_if_exists(notebook_execution_path)
    annotation_obj = read_json_if_exists(human_annotations_path)

    grounding_summary = (
        execution_obj.get("grounding_summary", {})
        if execution_obj and not execution_obj.get("_read_error")
        else {}
    )

    annotations = (
        annotation_obj.get("annotations", [])
        if annotation_obj and not annotation_obj.get("_read_error")
        else []
    )

    return {
        "article_id": article_id,
        "notebook_execution_path": str(notebook_execution_path),
        "human_annotations_path": str(human_annotations_path),

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

        "num_annotations": len(annotations),
        "num_grounding_annotations": sum(
            1 for a in annotations
            if a.get("annotation_scope") == "grounding"
        ),
        "num_final_decision_annotations": sum(
            1 for a in annotations
            if a.get("annotation_scope") == "final_decision"
        ),
        "num_empty_annotation_type": sum(
            1 for a in annotations
            if not str(a.get("annotation_type", "") or "").strip()
        ),
    }


def preview_rows_from_execution(
    article_id: str,
    notebook_execution_path: Path,
) -> List[Dict[str, Any]]:
    obj = read_json_if_exists(notebook_execution_path)

    if not obj or obj.get("_read_error"):
        return []

    rows = []

    for r in obj.get("preview_results", []) or []:
        rows.append(
            {
                "article_id": article_id,
                "logical_file_id": r.get("logical_file_id"),
                "logical_name": r.get("logical_name"),
                "grounding_status": r.get("grounding_status"),
                "relative_path": r.get("relative_path"),
                "absolute_path": r.get("absolute_path"),
                "match_score": r.get("match_score"),
                "match_type": r.get("match_type"),
                "preview_success": r.get("preview_success"),
                "error": r.get("error"),
                "num_preview_rows": r.get("num_preview_rows"),
                "num_preview_columns": r.get("num_preview_columns"),
                "columns": " | ".join(
                    str(c)
                    for c in r.get("columns", [])
                ),
            }
        )

    return rows


def annotation_rows_from_file(
    article_id: str,
    human_annotations_path: Path,
) -> List[Dict[str, Any]]:
    obj = read_json_if_exists(human_annotations_path)

    if not obj or obj.get("_read_error"):
        return []

    rows = []

    for a in obj.get("annotations", []) or []:
        rows.append(
            {
                "article_id": article_id,
                "annotation_id": a.get("annotation_id"),
                "annotation_scope": a.get("annotation_scope"),
                "target_id": a.get("target_id"),
                "target_type": a.get("target_type"),
                "logical_name": a.get("logical_name"),
                "system_status": a.get("system_status"),
                "default_action": a.get("default_action"),
                "annotation_type": a.get("annotation_type"),
                "human_decision": a.get("human_decision"),
                "selected_physical_file": a.get("selected_physical_file"),
                "comment": a.get("comment"),
                "curator_confidence": a.get("curator_confidence"),
                "timestamp": a.get("timestamp"),
                "candidate_physical_files": " | ".join(
                    str(x)
                    for x in a.get("candidate_physical_files", [])
                ),
                "system_matched_physical_files": " | ".join(
                    str(x)
                    for x in a.get("system_matched_physical_files", [])
                ),
                "system_grounding_score": a.get("system_grounding_score"),
                "system_recommendation": a.get("system_recommendation"),
                "human_final_decision": a.get("human_final_decision"),
            }
        )

    return rows


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
        "--log-path",
        type=Path,
    )

    args = parser.parse_args()

    benchmark_root = args.benchmark_root.resolve()

    setup_logging(
        args.log_path
        or benchmark_root / "export_notebook_review_manifests.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    article_rows: List[Dict[str, Any]] = []
    preview_rows: List[Dict[str, Any]] = []
    annotation_rows: List[Dict[str, Any]] = []

    for case in cases:
        article_rows.append(
            article_row_from_outputs(
                article_id=case.article_id,
                notebook_execution_path=case.notebook_execution_path,
                human_annotations_path=case.human_annotations_path,
            )
        )

        preview_rows.extend(
            preview_rows_from_execution(
                article_id=case.article_id,
                notebook_execution_path=case.notebook_execution_path,
            )
        )

        annotation_rows.extend(
            annotation_rows_from_file(
                article_id=case.article_id,
                human_annotations_path=case.human_annotations_path,
            )
        )

    if args.article_id:
        suffix = f"_{args.article_id}"
    else:
        suffix = ""

    article_manifest = (
        benchmark_root
        / f"curatability_notebook_execution_article_manifest{suffix}.csv"
    )
    preview_manifest = (
        benchmark_root
        / f"curatability_notebook_preview_manifest{suffix}.csv"
    )
    annotation_manifest = (
        benchmark_root
        / f"curatability_human_annotation_manifest{suffix}.csv"
    )

    write_manifest(article_rows, article_manifest)
    write_manifest(preview_rows, preview_manifest)
    write_manifest(annotation_rows, annotation_manifest)

    print(f"Wrote notebook execution article manifest: {article_manifest}")
    print(f"Wrote notebook preview manifest: {preview_manifest}")
    print(f"Wrote human annotation manifest: {annotation_manifest}")

    print("\nSummary")
    print("-------")
    print("articles:", len(article_rows))
    print("preview rows:", len(preview_rows))
    print("annotation rows:", len(annotation_rows))
    print(
        "preview success:",
        sum(
            1 for r in preview_rows
            if str(r.get("preview_success")).lower() == "true"
            or r.get("preview_success") is True
        ),
    )
    print(
        "preview failed:",
        sum(
            1 for r in preview_rows
            if str(r.get("preview_success")).lower() == "false"
            or r.get("preview_success") is False
        ),
    )


if __name__ == "__main__":
    main()
