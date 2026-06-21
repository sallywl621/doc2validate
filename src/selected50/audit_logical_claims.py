import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    load_logical_claims,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def is_unknown(value: Any) -> bool:
    if value is None:
        return True

    text = str(value).strip().lower()

    return text in {
        "",
        "unknown",
        "none",
        "null",
        "n/a",
        "na",
    }


def compute_logical_schema_score(row: Dict[str, Any]) -> float:
    """
    Documentation-claim completeness score.

    This is NOT final curatability.
    It only measures whether the logical schema is sufficient for
    grounding and notebook generation.
    """
    score = 0.0

    if row["num_logical_files"] > 0:
        score += 0.20

    if row["num_files_with_path_or_pattern"] > 0:
        score += 0.25

    if row["num_files_with_format"] > 0:
        score += 0.15

    if row["num_tabular_logical_claims"] > 0:
        score += 0.15

    if row["num_files_with_columns"] > 0:
        score += 0.20

    if row["structure_confidence_available"]:
        score += 0.05

    return round(score, 4)


def audit_logical_claims_for_case(case) -> Dict[str, Any]:
    logical = load_logical_claims(case)

    summary = logical.get("summary", {})
    logical_files = logical.get("logical_files", [])

    structure_confidence = logical.get("structure_confidence", "unknown")
    structure_confidence_available = not is_unknown(structure_confidence)

    num_primary_or_derived = 0
    num_metadata_or_annotation = 0

    num_columns_with_semantic_type = 0
    num_columns_with_description = 0

    warnings = []

    for f in logical_files:
        role = str(f.get("role", "unknown")).lower()

        if role in {"primary_data", "derived_data"}:
            num_primary_or_derived += 1

        if role in {"metadata", "annotation"}:
            num_metadata_or_annotation += 1

        for c in f.get("columns", []):
            if not is_unknown(c.get("semantic_type")):
                num_columns_with_semantic_type += 1

            if not is_unknown(c.get("description")):
                num_columns_with_description += 1

    row = {
        "article_id": case.article_id,
        "schema_path": logical.get("schema_path"),
        "schema_status": logical.get("schema_status"),

        "num_logical_files": summary.get("num_logical_files", 0),
        "num_files_with_path_or_pattern": summary.get("num_files_with_path_or_pattern", 0),
        "num_files_with_format": summary.get("num_files_with_format", 0),
        "num_tabular_logical_claims": summary.get("num_tabular_logical_claims", 0),
        "num_files_with_columns": summary.get("num_files_with_columns", 0),
        "total_documented_columns": summary.get("total_documented_columns", 0),

        "num_primary_or_derived_files": num_primary_or_derived,
        "num_metadata_or_annotation_files": num_metadata_or_annotation,
        "num_columns_with_semantic_type": num_columns_with_semantic_type,
        "num_columns_with_description": num_columns_with_description,

        "structure_confidence": structure_confidence,
        "structure_confidence_available": structure_confidence_available,
    }

    if row["num_logical_files"] == 0:
        warnings.append("no_logical_files")

    if row["num_files_with_path_or_pattern"] == 0:
        warnings.append("no_path_or_pattern")

    if row["num_files_with_format"] == 0:
        warnings.append("no_format")

    if row["num_tabular_logical_claims"] == 0:
        warnings.append("no_tabular_logical_claims")

    if row["num_files_with_columns"] == 0:
        warnings.append("no_column_semantics")

    if row["total_documented_columns"] > 0 and row["num_columns_with_semantic_type"] == 0:
        warnings.append("columns_without_semantic_type")

    row["logical_schema_score"] = compute_logical_schema_score(row)
    row["warnings"] = ";".join(warnings)

    return row


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
        or benchmark_root / "logical_claims_audit.log"
    )

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    rows: List[Dict[str, Any]] = []

    for case in cases:
        started = datetime.now().isoformat()

        try:
            row = audit_logical_claims_for_case(case)
            row["status"] = "success"
            row["error"] = ""

        except Exception as exc:
            row = {
                "article_id": case.article_id,
                "status": "error",
                "error": str(exc),
            }

        row["started_at"] = started
        row["finished_at"] = datetime.now().isoformat()

        rows.append(row)

    if args.manifest:
        out_manifest = args.manifest
    elif args.article_id:
        out_manifest = benchmark_root / f"logical_claims_audit_{args.article_id}.csv"
    else:
        out_manifest = benchmark_root / "logical_claims_audit.csv"

    write_manifest(rows, out_manifest)

    print(f"Wrote logical claims audit: {out_manifest}")

    ok_rows = [
        r for r in rows
        if r.get("status") == "success"
    ]

    print("\nSummary")
    print("-------")
    print("n cases:", len(rows))
    print("success:", len(ok_rows))
    print(
        "logical files > 0:",
        sum(1 for r in ok_rows if r.get("num_logical_files", 0) > 0),
    )
    print(
        "path/pattern > 0:",
        sum(1 for r in ok_rows if r.get("num_files_with_path_or_pattern", 0) > 0),
    )
    print(
        "format > 0:",
        sum(1 for r in ok_rows if r.get("num_files_with_format", 0) > 0),
    )
    print(
        "tabular claims > 0:",
        sum(1 for r in ok_rows if r.get("num_tabular_logical_claims", 0) > 0),
    )
    print(
        "columns > 0:",
        sum(1 for r in ok_rows if r.get("num_files_with_columns", 0) > 0),
    )
    print(
        "score >= 0.75:",
        sum(1 for r in ok_rows if r.get("logical_schema_score", 0) >= 0.75),
    )

    low_score = [
        r for r in ok_rows
        if r.get("logical_schema_score", 0) < 0.75
    ]

    print("\nLow-score cases:", len(low_score))

    for r in low_score[:20]:
        print(
            r["article_id"],
            "score=",
            r.get("logical_schema_score"),
            "warnings=",
            r.get("warnings", ""),
        )


if __name__ == "__main__":
    main()
