import argparse
from pathlib import Path
from typing import Any, Dict, List

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    read_json_if_exists,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def first_match_path(file_grounding: Dict[str, Any]) -> str:
    matched = file_grounding.get("matched_physical_files") or []

    if not matched:
        return ""

    return str(matched[0].get("relative_path", ""))


def first_match_score(file_grounding: Dict[str, Any]) -> Any:
    matched = file_grounding.get("matched_physical_files") or []

    if not matched:
        return ""

    return matched[0].get("match_score", "")


def first_match_type(file_grounding: Dict[str, Any]) -> str:
    matched = file_grounding.get("matched_physical_files") or []

    if not matched:
        return ""

    return str(matched[0].get("match_type", ""))


def article_row_from_grounding(
    article_id: str,
    obj: Dict[str, Any],
    path: Path,
) -> Dict[str, Any]:
    summary = obj.get("summary", {})
    logical_summary = obj.get("logical_summary", {})
    physical_summary = obj.get("physical_summary", {})
    input_layers = obj.get("input_layers", {})

    warning_counts = summary.get("warning_counts", {}) or {}

    return {
        "article_id": article_id,
        "grounding_path": str(path),
        "schema_version": obj.get("schema_version"),
        "generated_at": obj.get("generated_at"),

        "logical_schema_path": input_layers.get("logical_schema_path"),
        "effective_artifact_root": input_layers.get("effective_artifact_root"),
        "effective_artifact_source": input_layers.get("effective_artifact_source"),

        "num_logical_files": summary.get("num_logical_files"),
        "num_file_grounding_applicable": summary.get("num_file_grounding_applicable"),
        "num_resolved": summary.get("num_resolved"),
        "num_ambiguous": summary.get("num_ambiguous"),
        "num_weak_match": summary.get("num_weak_match"),
        "num_missing": summary.get("num_missing"),
        "num_ungroundable": summary.get("num_ungroundable"),
        "num_unsupported_non_file_claim": summary.get("num_unsupported_non_file_claim"),
        "num_human_review_needed": summary.get("num_human_review_needed"),
        "grounding_score": summary.get("grounding_score"),

        "logical_num_files": logical_summary.get("num_logical_files"),
        "logical_num_tabular_claims": logical_summary.get("num_tabular_logical_claims"),
        "logical_num_files_with_columns": logical_summary.get("num_files_with_columns"),
        "logical_total_documented_columns": logical_summary.get("total_documented_columns"),

        "physical_num_files": physical_summary.get("num_physical_files"),
        "physical_num_tabular_candidates": physical_summary.get("num_tabular_candidates"),

        "warning_missing_name_match_with_same_format_candidates": warning_counts.get(
            "missing_name_match_with_same_format_candidates",
            0,
        ),
        "warning_missing_physical_match": warning_counts.get(
            "missing_physical_match",
            0,
        ),
        "warning_ambiguous_physical_match": warning_counts.get(
            "ambiguous_physical_match",
            0,
        ),
        "warning_weak_physical_match": warning_counts.get(
            "weak_physical_match",
            0,
        ),
        "warning_ungroundable_logical_claim": warning_counts.get(
            "ungroundable_logical_claim",
            0,
        ),
        "warning_unsupported_non_file_claim": warning_counts.get(
            "unsupported_non_file_claim",
            0,
        ),
    }


def file_rows_from_grounding(
    article_id: str,
    obj: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = []

    for g in obj.get("file_groundings", []) or []:
        candidates = g.get("candidate_physical_files") or []
        warnings = g.get("warnings") or []

        rows.append(
            {
                "article_id": article_id,
                "logical_file_id": g.get("logical_file_id"),
                "logical_name": g.get("logical_name"),
                "documented_path_or_pattern": g.get("documented_path_or_pattern"),
                "expected_format": g.get("expected_format"),
                "schema_type": g.get("schema_type"),
                "role": g.get("role"),
                "num_documented_columns": g.get("num_documented_columns"),

                "grounding_status": g.get("grounding_status"),
                "human_review_needed": g.get("human_review_needed"),

                "matched_physical_file": first_match_path(g),
                "matched_score": first_match_score(g),
                "matched_type": first_match_type(g),

                "num_candidate_physical_files": len(candidates),
                "candidate_paths": " | ".join(
                    str(c.get("relative_path", ""))
                    for c in candidates
                ),
                "candidate_scores": " | ".join(
                    str(c.get("match_score", ""))
                    for c in candidates
                ),
                "candidate_match_types": " | ".join(
                    str(c.get("match_type", ""))
                    for c in candidates
                ),

                "warning_types": ";".join(
                    str(w.get("warning_type", "unknown"))
                    for w in warnings
                ),
                "warning_severities": ";".join(
                    str(w.get("severity", "unknown"))
                    for w in warnings
                ),
            }
        )

    return rows


def warning_rows_from_grounding(
    article_id: str,
    obj: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = []

    for g in obj.get("file_groundings", []) or []:
        for w in g.get("warnings", []) or []:
            rows.append(
                {
                    "article_id": article_id,
                    "warning_scope": "logical_file",
                    "logical_file_id": g.get("logical_file_id"),
                    "logical_name": g.get("logical_name"),
                    "documented_path_or_pattern": g.get("documented_path_or_pattern"),
                    "expected_format": g.get("expected_format"),
                    "schema_type": g.get("schema_type"),
                    "role": g.get("role"),
                    "grounding_status": g.get("grounding_status"),
                    "warning_type": w.get("warning_type"),
                    "severity": w.get("severity"),
                    "message": w.get("message"),
                }
            )

    for w in obj.get("global_warnings", []) or []:
        rows.append(
            {
                "article_id": article_id,
                "warning_scope": "global",
                "logical_file_id": "",
                "logical_name": "",
                "documented_path_or_pattern": "",
                "expected_format": "",
                "schema_type": "",
                "role": "",
                "grounding_status": "",
                "warning_type": w.get("warning_type"),
                "severity": w.get("severity"),
                "message": w.get("message"),
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
        or benchmark_root / "export_grounding_manifests.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    article_rows: List[Dict[str, Any]] = []
    file_rows: List[Dict[str, Any]] = []
    warning_rows: List[Dict[str, Any]] = []

    for case in cases:
        path = case.refined_grounding_path
        obj = read_json_if_exists(path)

        if not obj:
            article_rows.append(
                {
                    "article_id": case.article_id,
                    "grounding_path": str(path),
                    "status": "missing_grounding_json",
                }
            )
            continue

        if obj.get("_read_error"):
            article_rows.append(
                {
                    "article_id": case.article_id,
                    "grounding_path": str(path),
                    "status": "read_error",
                    "error": obj.get("_read_error"),
                }
            )
            continue

        article_row = article_row_from_grounding(
            article_id=case.article_id,
            obj=obj,
            path=path,
        )
        article_row["status"] = "success"

        article_rows.append(article_row)

        file_rows.extend(
            file_rows_from_grounding(
                article_id=case.article_id,
                obj=obj,
            )
        )

        warning_rows.extend(
            warning_rows_from_grounding(
                article_id=case.article_id,
                obj=obj,
            )
        )

    if args.article_id:
        suffix = f"_{args.article_id}"
    else:
        suffix = ""

    article_manifest = (
        benchmark_root
        / f"refined_artifact_grounding_article_manifest{suffix}.csv"
    )
    file_manifest = (
        benchmark_root
        / f"refined_artifact_grounding_file_manifest{suffix}.csv"
    )
    warning_manifest = (
        benchmark_root
        / f"refined_artifact_grounding_warning_manifest{suffix}.csv"
    )

    write_manifest(article_rows, article_manifest)
    write_manifest(file_rows, file_manifest)
    write_manifest(warning_rows, warning_manifest)

    print(f"Wrote article manifest: {article_manifest}")
    print(f"Wrote file manifest: {file_manifest}")
    print(f"Wrote warning manifest: {warning_manifest}")

    ok_articles = [
        r for r in article_rows
        if r.get("status") == "success"
    ]

    print("\nSummary")
    print("-------")
    print("articles:", len(article_rows))
    print("successful articles:", len(ok_articles))
    print("logical file rows:", len(file_rows))
    print("warning rows:", len(warning_rows))


if __name__ == "__main__":
    main()
