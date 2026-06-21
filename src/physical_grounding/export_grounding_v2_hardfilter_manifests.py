#!/usr/bin/env python3
"""Standalone exporter for grounding v2 hardfilter outputs.

This version exports three human-review target files:

1. file-level mapping review:
   presentation_grounding_v2_file_annotation_targets.csv

2. loader/header review for resolved files whose headers cannot be extracted:
   presentation_grounding_v2_loader_header_review_targets.csv

3. column-wise semantic/name review:
   presentation_grounding_v2_column_annotation_targets.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


def add_project_root(project_root: Path) -> None:
    project_root = project_root.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def write_manifest(rows: Iterable[Dict[str, Any]], path: Path) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def default_output_dir(benchmark_root: Path) -> Path:
    return benchmark_root / "grounding_v2_hardfilter_0618"


def article_json_path(output_dir: Path, article_id: str) -> Path:
    return output_dir / "json" / article_id / "refined_artifact_grounding_v2.json"


def _first_path(g: Dict[str, Any]) -> str:
    matched = g.get("matched_physical_files") or []
    candidates = g.get("candidate_physical_files") or []
    source = matched or candidates
    if not source:
        return ""
    return str(source[0].get("relative_path", ""))


def _get(d: Dict[str, Any], path: str, default: Any = "") -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part, default)
    return cur


def article_row(article_id: str, obj: Dict[str, Any], path: Path) -> Dict[str, Any]:
    summary = obj.get("summary", {}) or {}
    logical = obj.get("logical_summary", {}) or {}
    physical = obj.get("physical_summary", {}) or {}
    dim_counts = summary.get("dimension_status_counts", {}) or {}

    row = {
        "article_id": article_id,
        "grounding_path": str(path),
        "schema_version": obj.get("schema_version"),
        "num_logical_files": summary.get("num_logical_files"),
        "num_file_grounding_applicable": summary.get("num_file_grounding_applicable"),
        "num_human_review_needed": summary.get("num_human_review_needed"),
        "identity_grounding_score": summary.get("grounding_score"),
        "presentation_grounding_score": summary.get("presentation_grounding_score"),
        "num_column_grounding_applicable_files": summary.get("num_column_grounding_applicable"),
        "column_grounding_documented_columns": summary.get("total_documented_columns"),
        "total_matched_columns": summary.get("total_matched_columns"),
        "mean_file_column_coverage": summary.get("mean_file_column_coverage"),
        "overall_column_coverage": summary.get("overall_column_coverage"),
        "logical_total_documented_columns_all_files": logical.get("total_documented_columns"),
        "physical_num_files": physical.get("num_physical_files"),
        "physical_num_tabular_candidates": physical.get("num_tabular_candidates"),
    }

    for dim in ["identity", "format", "role", "columns"]:
        for status, count in (dim_counts.get(dim, {}) or {}).items():
            row[f"{dim}_status_{status}"] = count

    return row


def file_rows(article_id: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []

    for g in obj.get("file_groundings", []) or []:
        pg = g.get("presentation_grounding", {}) or {}
        at = g.get("annotation_target", {}) or {}

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
                "matched_or_candidate_path": _first_path(g),
                "grounding_status": g.get("grounding_status"),
                "human_review_needed": g.get("human_review_needed"),
                "identity_score": _get(g, "identity_grounding.score"),
                "identity_evidence_type": _get(g, "identity_grounding.evidence_type"),
                "format_status": _get(g, "format_grounding.status"),
                "format_score": _get(g, "format_grounding.score"),
                "observed_suffix": _get(g, "format_grounding.observed_suffix"),
                "header_load_status": _get(g, "format_grounding.header_load_status"),
                "role_status": _get(g, "role_grounding.status"),
                "role_score": _get(g, "role_grounding.score"),
                "column_status": _get(g, "column_grounding.status"),
                "column_score": _get(g, "column_grounding.score"),
                "num_observed_columns": _get(g, "column_grounding.num_observed_columns"),
                "num_matched_columns": _get(g, "column_grounding.num_matched_columns"),
                "column_coverage": _get(g, "column_grounding.coverage"),
                "presentation_grounding_score": pg.get("score"),
                "failed_dimensions": "|".join(pg.get("failed_dimensions", []) or []),
                "uncertain_dimensions": "|".join(pg.get("uncertain_dimensions", []) or []),
                "annotation_needs_review": at.get("needs_review"),
            }
        )

    return rows


def column_rows(article_id: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []

    for g in obj.get("file_groundings", []) or []:
        if g.get("grounding_status") != "resolved":
            continue

        cg = g.get("column_grounding", {}) or {}

        if cg.get("status") == "not_applicable_file_not_confirmed":
            continue

        for m in cg.get("matches", []) or []:
            rows.append(
                {
                    "article_id": article_id,
                    "logical_file_id": g.get("logical_file_id"),
                    "logical_name": g.get("logical_name"),
                    "matched_physical_file": _first_path(g),
                    "documented_column": m.get("documented_column"),
                    "matched_column": m.get("matched_column"),
                    "column_match_type": m.get("match_type"),
                    "column_match_score": m.get("score"),
                    "column_grounding_status": cg.get("status"),
                    "human_review_needed": float(m.get("score") or 0.0) < 0.65,
                }
            )

    return rows


def file_annotation_rows(article_id: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """File-level annotation targets: unresolved file identity mappings only."""
    rows = []

    for g in obj.get("file_groundings", []) or []:
        if g.get("grounding_status") == "resolved":
            continue

        at = g.get("annotation_target", {}) or {}

        rows.append(
            {
                "annotation_scope": "file_identity_grounding",
                "article_id": article_id,
                "logical_file_id": g.get("logical_file_id"),
                "logical_name": g.get("logical_name"),
                "documented_path_or_pattern": g.get("documented_path_or_pattern"),
                "expected_format": g.get("expected_format"),
                "role": g.get("role"),
                "num_documented_columns": g.get("num_documented_columns"),
                "matched_or_candidate_path": _first_path(g),
                "grounding_status": g.get("grounding_status"),
                "format_status": _get(g, "format_grounding.status"),
                "role_status": _get(g, "role_grounding.status"),
                "column_status": _get(g, "column_grounding.status"),
                "column_coverage": _get(g, "column_grounding.coverage"),
                "failed_dimensions": "identity",
                "uncertain_dimensions": "",
                "suggested_human_question": at.get("suggested_human_question")
                or (
                    "Is this unresolved file mapping caused by a documentation-artifact "
                    "mismatch, an LLM extraction error, a grounding algorithm error, "
                    "insufficient documentation, or an acceptable/manual mapping variant?"
                ),
                "human_error_source": "",
                "human_action": "",
                "human_notes": "",
                "annotator": "",
                "annotation_timestamp": "",
            }
        )

    return rows


def loader_header_review_rows(article_id: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Loader/header review targets:
      resolved files with documented columns but no observed headers.

    These should not be counted as column semantic mismatch.
    They require loader, unpacking, format-specific parsing, or representation review.
    """
    rows = []

    for g in obj.get("file_groundings", []) or []:
        if g.get("grounding_status") != "resolved":
            continue

        num_doc_cols = int(g.get("num_documented_columns") or 0)
        if num_doc_cols <= 0:
            continue

        cg = g.get("column_grounding", {}) or {}
        if cg.get("status") != "no_observed_headers":
            continue

        rows.append(
            {
                "annotation_scope": "loader_header_review",
                "article_id": article_id,
                "logical_file_id": g.get("logical_file_id"),
                "logical_name": g.get("logical_name"),
                "documented_path_or_pattern": g.get("documented_path_or_pattern"),
                "expected_format": g.get("expected_format"),
                "role": g.get("role"),
                "matched_physical_file": _first_path(g),
                "observed_suffix": _get(g, "format_grounding.observed_suffix"),
                "format_status": _get(g, "format_grounding.status"),
                "header_load_status": _get(g, "format_grounding.header_load_status"),
                "column_status": cg.get("status"),
                "num_documented_columns": num_doc_cols,
                "num_observed_columns": cg.get("num_observed_columns"),
                "suggested_human_question": (
                    "The file mapping is resolved, but observed headers could not be extracted. "
                    "Does this require archive unpacking, a specialized loader, format conversion, "
                    "or should it be excluded from column-wise validation?"
                ),
                "human_error_source": "",
                "human_action": "",
                "loader_or_format_note": "",
                "human_notes": "",
                "annotator": "",
                "annotation_timestamp": "",
            }
        )

    return rows


def column_annotation_rows(article_id: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Column-level annotation targets: weak/unmatched columns from resolved files only."""
    rows = []

    for g in obj.get("file_groundings", []) or []:
        if g.get("grounding_status") != "resolved":
            continue

        cg = g.get("column_grounding", {}) or {}

        if cg.get("status") == "not_applicable_file_not_confirmed":
            continue

        # If headers cannot be observed, this belongs to loader/header review,
        # not column semantic annotation.
        if cg.get("status") == "no_observed_headers":
            continue

        for m in cg.get("matches", []) or []:
            score = float(m.get("score") or 0.0)

            if score >= 0.65:
                continue

            rows.append(
                {
                    "annotation_scope": "column_grounding",
                    "article_id": article_id,
                    "logical_file_id": g.get("logical_file_id"),
                    "logical_name": g.get("logical_name"),
                    "matched_physical_file": _first_path(g),
                    "documented_column": m.get("documented_column"),
                    "matched_column": m.get("matched_column"),
                    "column_match_type": m.get("match_type"),
                    "column_match_score": score,
                    "column_grounding_status": cg.get("status"),
                    "suggested_human_question": (
                        "Is this documented column absent from the confirmed physical file, "
                        "an acceptable column-name variant, or an LLM extraction error?"
                    ),
                    "human_error_source": "",
                    "human_action": "",
                    "manual_column_mapping": "",
                    "human_notes": "",
                    "annotator": "",
                    "annotation_timestamp": "",
                }
            )

    return rows


def write_summary_json(
    output_dir: Path,
    article_out: List[Dict[str, Any]],
    file_out: List[Dict[str, Any]],
    column_out: List[Dict[str, Any]],
    file_ann: List[Dict[str, Any]],
    loader_ann: List[Dict[str, Any]],
    col_ann: List[Dict[str, Any]],
) -> None:
    def sum_int(rows: List[Dict[str, Any]], key: str) -> int:
        return int(sum(float(r.get(key) or 0) for r in rows))

    summary = {
        "n_articles": len(article_out),
        "file_manifest_rows": len(file_out),
        "column_manifest_rows": len(column_out),
        "file_annotation_target_rows": len(file_ann),
        "loader_header_review_target_rows": len(loader_ann),
        "loader_header_review_documented_columns": sum_int(loader_ann, "num_documented_columns"),
        "column_annotation_target_rows": len(col_ann),
        "column_grounding_documented_columns": sum_int(article_out, "column_grounding_documented_columns"),
        "total_matched_columns": sum_int(article_out, "total_matched_columns"),
    }

    path = output_dir / "manifests" / "presentation_grounding_v2_export_summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--article-id", type=str)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--output-dir", type=Path, help="Default: <benchmark-root>/grounding_v2_hardfilter_0618")

    args = parser.parse_args()

    add_project_root(args.project_root)

    from src.selected50.benchmark_loader import load_all_selected50_cases

    benchmark_root = args.benchmark_root.resolve()
    output_dir = (args.output_dir or default_output_dir(benchmark_root)).resolve()
    manifests_dir = output_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    article_out: List[Dict[str, Any]] = []
    file_out: List[Dict[str, Any]] = []
    column_out: List[Dict[str, Any]] = []
    file_annotation_out: List[Dict[str, Any]] = []
    loader_header_review_out: List[Dict[str, Any]] = []
    column_annotation_out: List[Dict[str, Any]] = []

    for case in cases:
        path = article_json_path(output_dir, case.article_id)
        obj = read_json(path)

        if not obj:
            article_out.append(
                {
                    "article_id": case.article_id,
                    "status": "missing_grounding_json",
                    "grounding_path": str(path),
                }
            )
            continue

        article_out.append(
            {
                "status": "success",
                **article_row(case.article_id, obj, path),
            }
        )

        file_out.extend(file_rows(case.article_id, obj))
        column_out.extend(column_rows(case.article_id, obj))
        file_annotation_out.extend(file_annotation_rows(case.article_id, obj))
        loader_header_review_out.extend(loader_header_review_rows(case.article_id, obj))
        column_annotation_out.extend(column_annotation_rows(case.article_id, obj))

    suffix = f"_{args.article_id}" if args.article_id else ""

    article_manifest = manifests_dir / f"presentation_grounding_v2_article_manifest{suffix}.csv"
    file_manifest = manifests_dir / f"presentation_grounding_v2_file_manifest{suffix}.csv"
    column_manifest = manifests_dir / f"presentation_grounding_v2_column_manifest{suffix}.csv"
    file_annotation_manifest = manifests_dir / f"presentation_grounding_v2_file_annotation_targets{suffix}.csv"
    loader_header_review_manifest = manifests_dir / f"presentation_grounding_v2_loader_header_review_targets{suffix}.csv"
    column_annotation_manifest = manifests_dir / f"presentation_grounding_v2_column_annotation_targets{suffix}.csv"

    write_manifest(article_out, article_manifest)
    write_manifest(file_out, file_manifest)
    write_manifest(column_out, column_manifest)
    write_manifest(file_annotation_out, file_annotation_manifest)
    write_manifest(loader_header_review_out, loader_header_review_manifest)
    write_manifest(column_annotation_out, column_annotation_manifest)

    write_summary_json(
        output_dir=output_dir,
        article_out=article_out,
        file_out=file_out,
        column_out=column_out,
        file_ann=file_annotation_out,
        loader_ann=loader_header_review_out,
        col_ann=column_annotation_out,
    )

    print(f"Wrote article manifest: {article_manifest}")
    print(f"Wrote file manifest: {file_manifest}")
    print(f"Wrote column manifest: {column_manifest}")
    print(f"Wrote file annotation targets: {file_annotation_manifest}")
    print(f"Wrote loader/header review targets: {loader_header_review_manifest}")
    print(f"Wrote column annotation targets: {column_annotation_manifest}")

    print("\nSummary")
    print("-------")
    print("articles:", len(article_out))
    print("file rows:", len(file_out))
    print("column rows:", len(column_out))
    print("file annotation target rows:", len(file_annotation_out))
    print("loader/header review target rows:", len(loader_header_review_out))
    print(
        "loader/header review documented columns:",
        sum(int(r.get("num_documented_columns") or 0) for r in loader_header_review_out),
    )
    print("column annotation target rows:", len(column_annotation_out))


if __name__ == "__main__":
    main()
