import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    load_grounding_inputs,
)

from src.utils.io import save_json, write_manifest
from src.utils.logging import setup_logging

# =========================
# ONLY CHANGE: IMPORT GROUNDING ENGINE
# =========================
from src.refine_artifact_grounding_v2.refine_grounder_v2 import RefinedArtifactGrounderV2


def manifest_row_from_result(
    article_id: str,
    result: Dict[str, Any],
    output_path: Path,
    status: str,
    error: str = "",
) -> Dict[str, Any]:

    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    logical_summary = result.get("logical_summary", {}) if isinstance(result, dict) else {}
    physical_summary = result.get("physical_summary", {}) if isinstance(result, dict) else {}

    return {
        "article_id": article_id,
        "status": status,
        "error": error,
        "output_path": str(output_path),

        "num_logical_files": logical_summary.get("num_logical_files"),
        "num_tabular_logical_claims": logical_summary.get("num_tabular_logical_claims"),
        "num_files_with_columns": logical_summary.get("num_files_with_columns"),
        "total_documented_columns": logical_summary.get("total_documented_columns"),

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
        "grounding_score": summary.get("grounding_score"),

        "warning_counts": summary.get("warning_counts"),

        # V2 extensions (safe add)
        "v2_column_audit": result.get("v2_column_audit"),
        "v2_llm_audit": result.get("v2_llm_audit"),
    }


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--article-id", type=str)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--max-artifact-files", type=int, default=5000)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)

    args = parser.parse_args()

    benchmark_root = args.benchmark_root.resolve()

    setup_logging(
        args.log_path or benchmark_root / "refined_artifact_grounding_v2.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    # =========================
    # ONLY CHANGE: GROUNDING ENGINE
    # =========================
    grounder = RefinedArtifactGrounderV2()

    rows: List[Dict[str, Any]] = []

    for case in cases:

        started_at = datetime.now().isoformat()
        output_path = case.refined_grounding_path

        if output_path.exists() and not args.overwrite:

            row = manifest_row_from_result(
                article_id=case.article_id,
                result={},
                output_path=output_path,
                status="skipped_exists",
            )

            row["started_at"] = started_at
            row["finished_at"] = datetime.now().isoformat()
            rows.append(row)
            continue

        try:

            grounding_inputs = load_grounding_inputs(
                case,
                max_artifact_files=args.max_artifact_files,
            )

            result = grounder.ground(grounding_inputs)

            save_json(result, output_path)

            row = manifest_row_from_result(
                article_id=case.article_id,
                result=result,
                output_path=output_path,
                status="success",
            )

        except Exception as exc:

            row = manifest_row_from_result(
                article_id=case.article_id,
                result={},
                output_path=output_path,
                status="error",
                error=str(exc),
            )

        row["started_at"] = started_at
        row["finished_at"] = datetime.now().isoformat()

        rows.append(row)

    # =========================
    # SAME OUTPUT LOGIC
    # =========================
    if args.manifest:
        out_manifest = args.manifest

    elif args.article_id:
        out_manifest = benchmark_root / f"refined_artifact_grounding_manifest_v2_{args.article_id}.csv"

    else:
        out_manifest = benchmark_root / "refined_artifact_grounding_manifest_v2.csv"

    write_manifest(rows, out_manifest)

    print(f"Wrote grounding V2 manifest: {out_manifest}")

    ok_rows = [r for r in rows if r.get("status") == "success"]

    print("\nSummary V2")
    print("-------")
    print("n cases:", len(rows))
    print("success:", len(ok_rows))

    print("resolved:", sum(int(r.get("num_resolved") or 0) for r in ok_rows))
    print("ambiguous:", sum(int(r.get("num_ambiguous") or 0) for r in ok_rows))
    print("weak_match:", sum(int(r.get("num_weak_match") or 0) for r in ok_rows))
    print("missing:", sum(int(r.get("num_missing") or 0) for r in ok_rows))

    if ok_rows:
        avg_score = sum(float(r.get("grounding_score") or 0.0) for r in ok_rows) / len(ok_rows)
        print("avg grounding_score:", round(avg_score, 4))


if __name__ == "__main__":
    main()
