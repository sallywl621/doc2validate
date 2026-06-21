#!/usr/bin/env python3
"""
Standalone Doc2Validate grounding v2 hardfilter runner.

This script does NOT need to be copied into src/ and does NOT overwrite v1 code.
It imports only the existing selected50 loader from your project root.

Example:
  python grounding_v2_standalone/run_grounding_v2.py \
    --project-root /mydata/doc2validate \
    --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
    --overwrite
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

# Local standalone grounder.
from grounder_v2_hardfilter import RefinedArtifactGrounder


def add_project_root(project_root: Path) -> None:
    project_root = project_root.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def save_json(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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


def default_output_dir(benchmark_root: Path) -> Path:
    return benchmark_root / "grounding_v2_hardfilter_0618"


def article_json_path(output_dir: Path, article_id: str) -> Path:
    return output_dir / "json" / article_id / "refined_artifact_grounding_v2.json"


def manifest_row_from_result(article_id: str, result: Dict[str, Any], output_path: Path, status: str, error: str = "") -> Dict[str, Any]:
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    logical_summary = result.get("logical_summary", {}) if isinstance(result, dict) else {}
    physical_summary = result.get("physical_summary", {}) if isinstance(result, dict) else {}

    return {
        "article_id": article_id,
        "status": status,
        "error": error,
        "output_path": str(output_path),
        "schema_version": result.get("schema_version") if isinstance(result, dict) else "",
        "num_logical_files": logical_summary.get("num_logical_files"),
        "num_tabular_logical_claims": logical_summary.get("num_tabular_logical_claims"),
        "num_files_with_columns": logical_summary.get("num_files_with_columns"),
        "total_documented_columns_all_logical_files": logical_summary.get("total_documented_columns"),
        "num_physical_files": physical_summary.get("num_physical_files"),
        "num_tabular_candidates": physical_summary.get("num_tabular_candidates"),
        "num_file_grounding_applicable": summary.get("num_file_grounding_applicable"),
        "num_resolved": summary.get("num_resolved"),
        "num_ambiguous": summary.get("num_ambiguous"),
        "num_weak_match": summary.get("num_weak_match"),
        "num_missing": summary.get("num_missing"),
        "num_ungroundable": summary.get("num_ungroundable"),
        "num_unsupported_non_file_claim": summary.get("num_unsupported_non_file_claim"),
        "num_human_review_needed": summary.get("num_human_review_needed"),
        "identity_grounding_score": summary.get("grounding_score"),
        "presentation_grounding_score": summary.get("presentation_grounding_score"),
        "num_column_grounding_applicable_files": summary.get("num_column_grounding_applicable"),
        "column_grounding_documented_columns": summary.get("total_documented_columns"),
        "total_matched_columns": summary.get("total_matched_columns"),
        "mean_file_column_coverage": summary.get("mean_file_column_coverage"),
        "overall_column_coverage": summary.get("overall_column_coverage"),
        "warning_counts": json.dumps(summary.get("warning_counts", {}), ensure_ascii=False),
        "dimension_status_counts": json.dumps(summary.get("dimension_status_counts", {}), ensure_ascii=False),
    }


def write_run_summary(rows: List[Dict[str, Any]], output_dir: Path) -> None:
    ok_rows = [r for r in rows if r.get("status") in {"success", "skipped_exists"}]

    def sum_int(key: str) -> int:
        return int(sum(float(r.get(key) or 0) for r in ok_rows))

    def mean_float(key: str) -> float:
        vals = [float(r.get(key)) for r in ok_rows if r.get(key) not in [None, ""]]
        return round(sum(vals) / len(vals), 6) if vals else 0.0

    summary = {
        "generated_at": datetime.now().isoformat(),
        "n_cases": len(rows),
        "success_or_skipped": len(ok_rows),
        "errors": len(rows) - len(ok_rows),
        "num_logical_files": sum_int("num_logical_files"),
        "num_tabular_logical_claims": sum_int("num_tabular_logical_claims"),
        "num_files_with_columns": sum_int("num_files_with_columns"),
        "total_documented_columns_all_logical_files": sum_int("total_documented_columns_all_logical_files"),
        "num_physical_files": sum_int("num_physical_files"),
        "num_tabular_candidates": sum_int("num_tabular_candidates"),
        "num_file_grounding_applicable": sum_int("num_file_grounding_applicable"),
        "num_resolved": sum_int("num_resolved"),
        "num_ambiguous": sum_int("num_ambiguous"),
        "num_weak_match": sum_int("num_weak_match"),
        "num_missing": sum_int("num_missing"),
        "num_unsupported_non_file_claim": sum_int("num_unsupported_non_file_claim"),
        "num_human_review_needed": sum_int("num_human_review_needed"),
        "mean_identity_grounding_score": mean_float("identity_grounding_score"),
        "mean_presentation_grounding_score": mean_float("presentation_grounding_score"),
        "num_column_grounding_applicable_files": sum_int("num_column_grounding_applicable_files"),
        "column_grounding_documented_columns": sum_int("column_grounding_documented_columns"),
        "total_matched_columns": sum_int("total_matched_columns"),
        "mean_file_column_coverage": mean_float("mean_file_column_coverage"),
        "mean_overall_column_coverage": mean_float("overall_column_coverage"),
    }

    path = output_dir / "manifests" / "refined_artifact_grounding_v2_run_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True, help="Doc2Validate project root, e.g. /mydata/doc2validate")
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--article-id", type=str)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--max-artifact-files", type=int, default=5000)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-dir", type=Path, help="Default: <benchmark-root>/grounding_v2")
    args = parser.parse_args()

    add_project_root(args.project_root)
    from src.selected50.benchmark_loader import load_all_selected50_cases, load_grounding_inputs

    benchmark_root = args.benchmark_root.resolve()
    output_dir = (args.output_dir or default_output_dir(benchmark_root)).resolve()
    (output_dir / "json").mkdir(parents=True, exist_ok=True)
    (output_dir / "manifests").mkdir(parents=True, exist_ok=True)

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    grounder = RefinedArtifactGrounder()
    rows: List[Dict[str, Any]] = []

    for case in cases:
        started_at = datetime.now().isoformat()
        output_path = article_json_path(output_dir, case.article_id)

        if output_path.exists() and not args.overwrite:
            obj = json.loads(output_path.read_text(encoding="utf-8"))
            row = manifest_row_from_result(case.article_id, obj, output_path, "skipped_exists")
            row["started_at"] = started_at
            row["finished_at"] = datetime.now().isoformat()
            rows.append(row)
            continue

        try:
            grounding_inputs = load_grounding_inputs(case, max_artifact_files=args.max_artifact_files)
            result = grounder.ground(grounding_inputs)
            save_json(result, output_path)
            row = manifest_row_from_result(case.article_id, result, output_path, "success")
        except Exception as exc:  # noqa: BLE001
            row = manifest_row_from_result(case.article_id, {}, output_path, "error", error=str(exc))

        row["started_at"] = started_at
        row["finished_at"] = datetime.now().isoformat()
        rows.append(row)

    if args.article_id:
        manifest_path = output_dir / "manifests" / f"refined_artifact_grounding_v2_run_manifest_{args.article_id}.csv"
    else:
        manifest_path = output_dir / "manifests" / "refined_artifact_grounding_v2_run_manifest.csv"

    write_manifest(rows, manifest_path)
    write_run_summary(rows, output_dir)

    success_rows = [r for r in rows if r.get("status") == "success"]
    skipped_rows = [r for r in rows if r.get("status") == "skipped_exists"]
    error_rows = [r for r in rows if r.get("status") == "error"]
    ok_rows = success_rows + skipped_rows
    print(f"Wrote v2 grounding manifest: {manifest_path}")
    print(f"Output directory: {output_dir}")
    print("\nSummary")
    print("-------")
    print("n cases:", len(rows))
    print("success:", len(success_rows))
    print("skipped_exists:", len(skipped_rows))
    print("errors:", len(error_rows))
    print("resolved:", sum(int(float(r.get("num_resolved") or 0)) for r in ok_rows))
    print("human_review_needed:", sum(int(float(r.get("num_human_review_needed") or 0)) for r in ok_rows))
    print("column_grounding_documented_columns:", sum(int(float(r.get("column_grounding_documented_columns") or 0)) for r in ok_rows))


if __name__ == "__main__":
    main()
