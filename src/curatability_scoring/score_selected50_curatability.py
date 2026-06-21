import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    load_logical_claims,
    read_json_if_exists,
    summarize_logical_claims,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


PREVIEW_CATEGORY_WEIGHTS = {
    # Generic tabular preview succeeded.
    "tabular_preview_success": 1.00,

    # These are repairable or inspectable with modest additional support.
    "missing_optional_dependency_xlrd": 0.70,
    "csv_encoding_error": 0.55,
    "archive_artifact_requires_unpacking": 0.40,
    "specialized_data_format_requires_loader": 0.35,

    # These may be useful stewardship evidence but are not directly tabular.
    "structured_metadata_not_tabular": 0.30,
    "document_or_text_artifact_not_tabular": 0.20,
    "code_or_notebook_artifact_not_tabular": 0.20,
    "image_artifact_not_tabular": 0.10,

    # Catch-all.
    "missing_or_unrecognized_suffix": 0.05,
    "unsupported_format": 0.00,
}


COMPONENT_WEIGHTS = {
    "logical_schema_score": 0.20,
    "physical_grounding_score": 0.30,
    "executable_preview_score": 0.20,
    "review_burden_score": 0.20,
    "intervention_need_score": 0.10,
}


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    try:
        if value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        if value == "":
            return default
        return float(value)
    except Exception:
        return default


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def bool_from_cell(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    s = str(value).strip().lower()

    return s in {"true", "1", "yes", "y"}


def extract_suffix(path_value: Any) -> str:
    s = str(path_value or "")

    name = Path(s).name

    if "." not in name:
        return ""

    return "." + name.split(".")[-1].lower()


def classify_preview_row(row: Dict[str, Any]) -> str:
    if bool_from_cell(row.get("preview_success")):
        return "tabular_preview_success"

    suffix = str(row.get("suffix") or "").strip().lower()

    if not suffix:
        suffix = extract_suffix(row.get("relative_path"))

    error = str(row.get("error") or "")

    if "codec can't decode" in error:
        return "csv_encoding_error"

    if "Missing optional dependency 'xlrd'" in error:
        return "missing_optional_dependency_xlrd"

    if suffix in {".zip", ".rar", ".gz"}:
        return "archive_artifact_requires_unpacking"

    if suffix in {
        ".py",
        ".r",
        ".rmd",
        ".ipynb",
        ".do",
        ".php",
        ".bash",
        ".qmd",
    }:
        return "code_or_notebook_artifact_not_tabular"

    if suffix in {
        ".pdf",
        ".docx",
        ".md",
        ".txt",
        ".html",
        ".ris",
    }:
        return "document_or_text_artifact_not_tabular"

    if suffix in {
        ".png",
        ".jpg",
        ".jpeg",
    }:
        return "image_artifact_not_tabular"

    if suffix in {
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".xml",
    }:
        return "structured_metadata_not_tabular"

    if suffix in {
        ".rda",
        ".rds",
        ".pkl",
        ".dta",
        ".fst",
        ".nc",
        ".sqlite",
        ".sql",
        ".gpkg",
    }:
        return "specialized_data_format_requires_loader"

    if not suffix:
        return "missing_or_unrecognized_suffix"

    return "unsupported_format"


def group_rows_by_article(
    rows: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in rows:
        article_id = str(row.get("article_id") or "").strip()

        if article_id:
            grouped[article_id].append(row)

    return dict(grouped)


def is_meaningful_value(value: Any) -> bool:
    if value is None:
        return False

    s = str(value).strip().lower()

    return s not in {
        "",
        "unknown",
        "none",
        "null",
        "n/a",
        "na",
        "not specified",
        "not_provided",
    }


def get_field(obj: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(field_name, default)

    return getattr(obj, field_name, default)


def summarize_logical_claims_flexible(
    loaded_claims: Any,
) -> Dict[str, Any]:
    """
    Robustly summarize logical claims regardless of whether
    load_logical_claims(case) returns:

      - List[LogicalFileClaim]
      - {"logical_files": [...]}
      - {"files": [...]}
      - {"claims": [...]}
      - {"summary": {...}}

    This avoids passing a dict directly into summarize_logical_claims().
    """
    if isinstance(loaded_claims, dict):
        existing_summary = loaded_claims.get("summary")

        if isinstance(existing_summary, dict):
            return existing_summary

        files = (
            loaded_claims.get("logical_files")
            or loaded_claims.get("files")
            or loaded_claims.get("claims")
            or []
        )

    else:
        files = loaded_claims

    if files is None:
        files = []

    # First try the canonical benchmark_loader summarizer.
    try:
        return summarize_logical_claims(files)
    except Exception:
        pass

    # Fallback summarizer for dict-like logical files.
    files = list(files)

    num_logical_files = len(files)

    num_files_with_path_or_pattern = 0
    num_files_with_format = 0
    num_tabular_logical_claims = 0
    num_files_with_columns = 0
    total_documented_columns = 0

    for f in files:
        documented_path_or_pattern = (
            get_field(f, "documented_path_or_pattern")
            or get_field(f, "path")
            or get_field(f, "path_or_pattern")
            or get_field(f, "filename")
            or get_field(f, "file_name")
            or get_field(f, "logical_name")
        )

        expected_format = (
            get_field(f, "expected_format")
            or get_field(f, "format")
            or get_field(f, "file_format")
        )

        schema_type = (
            get_field(f, "schema_type")
            or get_field(f, "type")
            or ""
        )

        columns = (
            get_field(f, "columns")
            or get_field(f, "documented_columns")
            or []
        )

        if is_meaningful_value(documented_path_or_pattern):
            num_files_with_path_or_pattern += 1

        if is_meaningful_value(expected_format):
            num_files_with_format += 1

        expected_format_str = str(expected_format or "").lower()
        schema_type_str = str(schema_type or "").lower()

        if (
            "tabular" in schema_type_str
            or expected_format_str in {
                "csv",
                "tsv",
                "xlsx",
                "xls",
                "parquet",
                "table",
            }
            or expected_format_str.endswith(".csv")
            or expected_format_str.endswith(".tsv")
            or expected_format_str.endswith(".xlsx")
            or expected_format_str.endswith(".xls")
        ):
            num_tabular_logical_claims += 1

        if isinstance(columns, dict):
            column_count = len(columns)
        elif isinstance(columns, list):
            column_count = len(columns)
        else:
            column_count = 0

        if column_count > 0:
            num_files_with_columns += 1
            total_documented_columns += column_count

    return {
        "num_logical_files": num_logical_files,
        "num_files_with_path_or_pattern": num_files_with_path_or_pattern,
        "num_files_with_format": num_files_with_format,
        "num_tabular_logical_claims": num_tabular_logical_claims,
        "num_files_with_columns": num_files_with_columns,
        "total_documented_columns": total_documented_columns,
    }


def load_logical_summary_for_case(case: Any) -> Dict[str, Any]:
    loaded_claims = load_logical_claims(case)
    return summarize_logical_claims_flexible(loaded_claims)


def score_logical_schema(
    logical_summary: Dict[str, Any],
) -> Dict[str, Any]:
    num_files = safe_int(logical_summary.get("num_logical_files"))

    if num_files <= 0:
        return {
            "score": 0.0,
            "details": {
                "reason": "no_logical_files",
            },
        }

    path_rate = safe_int(
        logical_summary.get("num_files_with_path_or_pattern")
    ) / num_files

    format_rate = safe_int(
        logical_summary.get("num_files_with_format")
    ) / num_files

    column_rate = safe_int(
        logical_summary.get("num_files_with_columns")
    ) / num_files

    score = (
        0.40 * path_rate
        + 0.30 * format_rate
        + 0.30 * column_rate
    )

    return {
        "score": clamp01(score),
        "details": {
            "num_logical_files": num_files,
            "path_pattern_rate": path_rate,
            "format_rate": format_rate,
            "column_rate": column_rate,
        },
    }


def score_physical_grounding(
    grounding_summary: Dict[str, Any],
) -> Dict[str, Any]:
    score = safe_float(grounding_summary.get("grounding_score"))

    return {
        "score": clamp01(score),
        "details": {
            "num_file_grounding_applicable": grounding_summary.get(
                "num_file_grounding_applicable"
            ),
            "num_resolved": grounding_summary.get("num_resolved"),
            "num_ambiguous": grounding_summary.get("num_ambiguous"),
            "num_weak_match": grounding_summary.get("num_weak_match"),
            "num_missing": grounding_summary.get("num_missing"),
            "num_unsupported_non_file_claim": grounding_summary.get(
                "num_unsupported_non_file_claim"
            ),
        },
    }


def score_executable_preview(
    preview_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not preview_rows:
        return {
            "score": 0.0,
            "details": {
                "num_preview_rows": 0,
                "reason": "no_preview_attempts",
            },
        }

    category_counts = Counter()
    weighted_sum = 0.0

    for row in preview_rows:
        category = row.get("preview_outcome_category")

        if not category:
            category = classify_preview_row(row)

        category_counts[category] += 1
        weighted_sum += PREVIEW_CATEGORY_WEIGHTS.get(category, 0.0)

    score = weighted_sum / len(preview_rows)

    return {
        "score": clamp01(score),
        "details": {
            "num_preview_rows": len(preview_rows),
            "category_counts": dict(category_counts),
            "category_weights": PREVIEW_CATEGORY_WEIGHTS,
        },
    }


def score_review_burden(
    grounding_summary: Dict[str, Any],
) -> Dict[str, Any]:
    num_logical_files = safe_int(grounding_summary.get("num_logical_files"))
    num_review = safe_int(grounding_summary.get("num_human_review_needed"))

    if num_logical_files <= 0:
        return {
            "score": 0.0,
            "details": {
                "reason": "no_logical_files",
            },
        }

    review_rate = num_review / num_logical_files
    score = 1.0 - review_rate

    return {
        "score": clamp01(score),
        "details": {
            "num_logical_files": num_logical_files,
            "num_human_review_needed": num_review,
            "review_rate": review_rate,
        },
    }


def score_intervention_need(
    grounding_summary: Dict[str, Any],
    preview_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Estimate how much curator intervention is likely required.

    Higher score means less intervention needed.

    This intentionally overlaps partly with grounding and preview, but makes
    the expected curator workload explicit.
    """
    num_logical_files = safe_int(grounding_summary.get("num_logical_files"))

    if num_logical_files <= 0:
        return {
            "score": 0.0,
            "details": {
                "reason": "no_logical_files",
            },
        }

    missing = safe_int(grounding_summary.get("num_missing"))
    ambiguous = safe_int(grounding_summary.get("num_ambiguous"))
    weak = safe_int(grounding_summary.get("num_weak_match"))
    unsupported = safe_int(
        grounding_summary.get("num_unsupported_non_file_claim")
    )

    grounding_intervention_points = (
        1.00 * missing
        + 0.60 * ambiguous
        + 0.40 * weak
        + 0.80 * unsupported
    )

    grounding_intervention_rate = grounding_intervention_points / num_logical_files

    preview_penalties = []

    for row in preview_rows:
        category = row.get("preview_outcome_category")

        if not category:
            category = classify_preview_row(row)

        weight = PREVIEW_CATEGORY_WEIGHTS.get(category, 0.0)
        preview_penalties.append(1.0 - weight)

    if preview_penalties:
        preview_intervention_rate = sum(preview_penalties) / len(preview_penalties)
    else:
        preview_intervention_rate = 1.0

    combined_intervention_rate = (
        0.70 * grounding_intervention_rate
        + 0.30 * preview_intervention_rate
    )

    score = 1.0 - combined_intervention_rate

    return {
        "score": clamp01(score),
        "details": {
            "grounding_intervention_points": grounding_intervention_points,
            "grounding_intervention_rate": grounding_intervention_rate,
            "preview_intervention_rate": preview_intervention_rate,
            "combined_intervention_rate": combined_intervention_rate,
            "num_missing": missing,
            "num_ambiguous": ambiguous,
            "num_weak_match": weak,
            "num_unsupported_non_file_claim": unsupported,
            "num_preview_rows": len(preview_rows),
        },
    }


def compute_overall_score(
    component_scores: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    weighted_sum = 0.0
    weight_sum = 0.0
    component_rows = []

    for component_name, weight in COMPONENT_WEIGHTS.items():
        score = safe_float(
            component_scores.get(component_name, {}).get("score")
        )

        weighted = score * weight

        weighted_sum += weighted
        weight_sum += weight

        component_rows.append(
            {
                "component": component_name,
                "score": score,
                "weight": weight,
                "weighted_contribution": weighted,
            }
        )

    overall = weighted_sum / weight_sum if weight_sum else 0.0

    return {
        "overall_score": clamp01(overall),
        "component_rows": component_rows,
    }


def recommendation_from_score(score: float) -> str:
    score = clamp01(score)

    if score >= 0.75:
        return "accept_for_ingest_with_light_review"

    if score >= 0.55:
        return "accept_with_curator_review"

    if score >= 0.35:
        return "request_supplementary_materials_or_manual_mapping"

    return "high_risk_manual_review"


def issue_rows_from_report(
    article_id: str,
    report: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = []

    grounding = report.get("evidence_counts", {}).get("grounding", {})
    preview_counts = report.get("evidence_counts", {}).get("preview_outcome_counts", {})

    for key in [
        "num_missing",
        "num_ambiguous",
        "num_weak_match",
        "num_unsupported_non_file_claim",
    ]:
        count = safe_int(grounding.get(key))

        if count > 0:
            rows.append(
                {
                    "article_id": article_id,
                    "issue_scope": "physical_grounding",
                    "issue_type": key,
                    "count": count,
                    "severity": (
                        "high"
                        if key in {
                            "num_missing",
                            "num_unsupported_non_file_claim",
                        }
                        else "medium"
                    ),
                }
            )

    for category, count in preview_counts.items():
        count = safe_int(count)

        if category == "tabular_preview_success":
            continue

        severity = "medium"

        if category in {
            "csv_encoding_error",
            "missing_optional_dependency_xlrd",
        }:
            severity = "low"

        if category in {
            "unsupported_format",
            "missing_or_unrecognized_suffix",
        }:
            severity = "high"

        rows.append(
            {
                "article_id": article_id,
                "issue_scope": "executable_preview",
                "issue_type": category,
                "count": count,
                "severity": severity,
            }
        )

    return rows


def score_case(
    case: Any,
    preview_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    logical_summary = load_logical_summary_for_case(case)

    grounding = read_json_if_exists(case.refined_grounding_path)

    if not grounding or grounding.get("_read_error"):
        grounding_summary = {}
    else:
        grounding_summary = grounding.get("summary", {})

    notebook_execution = read_json_if_exists(case.notebook_execution_path)
    human_annotations = read_json_if_exists(case.human_annotations_path)

    logical_schema_score = score_logical_schema(logical_summary)
    physical_grounding_score = score_physical_grounding(grounding_summary)
    executable_preview_score = score_executable_preview(preview_rows)
    review_burden_score = score_review_burden(grounding_summary)
    intervention_need_score = score_intervention_need(
        grounding_summary=grounding_summary,
        preview_rows=preview_rows,
    )

    component_scores = {
        "logical_schema_score": logical_schema_score,
        "physical_grounding_score": physical_grounding_score,
        "executable_preview_score": executable_preview_score,
        "review_burden_score": review_burden_score,
        "intervention_need_score": intervention_need_score,
    }

    overall = compute_overall_score(component_scores)
    overall_score = overall["overall_score"]

    annotation_rows = (
        human_annotations.get("annotations", [])
        if human_annotations and not human_annotations.get("_read_error")
        else []
    )

    preview_category_counts = Counter()

    for row in preview_rows:
        category = row.get("preview_outcome_category")

        if not category:
            category = classify_preview_row(row)

        preview_category_counts[category] += 1

    report = {
        "article_id": case.article_id,
        "created_at": datetime.now().isoformat(),
        "method": {
            "version": "curatability_scoring_v1",
            "component_weights": COMPONENT_WEIGHTS,
            "preview_category_weights": PREVIEW_CATEGORY_WEIGHTS,
            "interpretation": (
                "Higher scores indicate lower expected curator workload "
                "and lower executable validation risk. Scores are intended "
                "as transparent decision-support signals, not autonomous "
                "accept/reject decisions."
            ),
        },
        "inputs": {
            "dataset_structure_path": str(case.dataset_structure_path),
            "refined_grounding_path": str(case.refined_grounding_path),
            "notebook_execution_path": str(case.notebook_execution_path),
            "human_annotations_path": str(case.human_annotations_path),
        },
        "component_scores": component_scores,
        "overall_score": overall_score,
        "recommendation": recommendation_from_score(overall_score),
        "evidence_counts": {
            "logical_schema": logical_summary,
            "grounding": grounding_summary,
            "notebook_execution": {
                "exists": case.notebook_execution_path.exists(),
                "num_preview_results": (
                    notebook_execution.get("num_preview_results")
                    if notebook_execution and not notebook_execution.get("_read_error")
                    else None
                ),
                "num_preview_success": (
                    notebook_execution.get("num_preview_success")
                    if notebook_execution and not notebook_execution.get("_read_error")
                    else None
                ),
                "num_preview_failed": (
                    notebook_execution.get("num_preview_failed")
                    if notebook_execution and not notebook_execution.get("_read_error")
                    else None
                ),
            },
            "preview_outcome_counts": dict(preview_category_counts),
            "human_annotations": {
                "exists": case.human_annotations_path.exists(),
                "num_annotations": len(annotation_rows),
                "num_grounding_annotations": sum(
                    1
                    for a in annotation_rows
                    if a.get("annotation_scope") == "grounding"
                ),
                "num_final_decision_annotations": sum(
                    1
                    for a in annotation_rows
                    if a.get("annotation_scope") == "final_decision"
                ),
                "num_empty_annotation_type": sum(
                    1
                    for a in annotation_rows
                    if not str(a.get("annotation_type", "") or "").strip()
                ),
            },
        },
    }

    return report


def summary_row_from_report(report: Dict[str, Any]) -> Dict[str, Any]:
    scores = report.get("component_scores", {})
    evidence = report.get("evidence_counts", {})
    grounding = evidence.get("grounding", {})
    preview_counts = evidence.get("preview_outcome_counts", {})
    annotations = evidence.get("human_annotations", {})

    return {
        "article_id": report.get("article_id"),
        "overall_score": report.get("overall_score"),
        "recommendation": report.get("recommendation"),

        "logical_schema_score": scores.get("logical_schema_score", {}).get("score"),
        "physical_grounding_score": scores.get("physical_grounding_score", {}).get("score"),
        "executable_preview_score": scores.get("executable_preview_score", {}).get("score"),
        "review_burden_score": scores.get("review_burden_score", {}).get("score"),
        "intervention_need_score": scores.get("intervention_need_score", {}).get("score"),

        "num_logical_files": grounding.get("num_logical_files"),
        "num_file_grounding_applicable": grounding.get("num_file_grounding_applicable"),
        "num_resolved": grounding.get("num_resolved"),
        "num_ambiguous": grounding.get("num_ambiguous"),
        "num_weak_match": grounding.get("num_weak_match"),
        "num_missing": grounding.get("num_missing"),
        "num_unsupported_non_file_claim": grounding.get("num_unsupported_non_file_claim"),
        "num_human_review_needed": grounding.get("num_human_review_needed"),

        "num_preview_rows": sum(
            safe_int(v)
            for v in preview_counts.values()
        ),
        "num_tabular_preview_success": preview_counts.get(
            "tabular_preview_success", 0
        ),
        "num_csv_encoding_error": preview_counts.get(
            "csv_encoding_error", 0
        ),
        "num_archive_artifact_requires_unpacking": preview_counts.get(
            "archive_artifact_requires_unpacking", 0
        ),
        "num_specialized_data_format_requires_loader": preview_counts.get(
            "specialized_data_format_requires_loader", 0
        ),
        "num_code_or_notebook_artifact_not_tabular": preview_counts.get(
            "code_or_notebook_artifact_not_tabular", 0
        ),
        "num_document_or_text_artifact_not_tabular": preview_counts.get(
            "document_or_text_artifact_not_tabular", 0
        ),

        "num_annotations": annotations.get("num_annotations"),
        "num_grounding_annotations": annotations.get("num_grounding_annotations"),
        "num_final_decision_annotations": annotations.get(
            "num_final_decision_annotations"
        ),
        "num_empty_annotation_type": annotations.get("num_empty_annotation_type"),
    }


def component_rows_from_report(
    report: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = []

    article_id = report.get("article_id")
    component_scores = report.get("component_scores", {})

    for component_name, obj in component_scores.items():
        score = safe_float(obj.get("score"))
        weight = COMPONENT_WEIGHTS.get(component_name, 0.0)

        rows.append(
            {
                "article_id": article_id,
                "component": component_name,
                "score": score,
                "weight": weight,
                "weighted_contribution": score * weight,
                "details_json": json.dumps(
                    obj.get("details", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )

    return rows


def write_report(
    report: Dict[str, Any],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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
        "--preview-manifest",
        type=Path,
        help=(
            "Optional classified preview manifest. Defaults to "
            "curatability_notebook_preview_manifest_classified.csv if present, "
            "else curatability_notebook_preview_manifest.csv."
        ),
    )

    parser.add_argument(
        "--summary-csv",
        type=Path,
    )

    parser.add_argument(
        "--component-csv",
        type=Path,
    )

    parser.add_argument(
        "--issue-csv",
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
        or benchmark_root / "score_selected50_curatability.log"
    )

    if args.preview_manifest:
        preview_manifest = args.preview_manifest
    else:
        classified = benchmark_root / "curatability_notebook_preview_manifest_classified.csv"
        raw = benchmark_root / "curatability_notebook_preview_manifest.csv"

        if classified.exists():
            preview_manifest = classified
        else:
            preview_manifest = raw

    preview_rows = read_csv_rows(preview_manifest)
    preview_by_article = group_rows_by_article(preview_rows)

    cases = load_all_selected50_cases(
        benchmark_root=benchmark_root,
        article_id=args.article_id,
        max_articles=args.max_articles,
    )

    summary_rows: List[Dict[str, Any]] = []
    component_rows: List[Dict[str, Any]] = []
    issue_rows: List[Dict[str, Any]] = []

    for case in cases:
        case_preview_rows = preview_by_article.get(case.article_id, [])

        report = score_case(
            case=case,
            preview_rows=case_preview_rows,
        )

        json_dir = getattr(case, "json_dir", None)

        if json_dir is None:
            json_dir = Path(case.dataset_structure_path).parent

        report_path = Path(json_dir) / "curatability_report.json"

        write_report(report, report_path)

        summary_rows.append(summary_row_from_report(report))
        component_rows.extend(component_rows_from_report(report))
        issue_rows.extend(issue_rows_from_report(case.article_id, report))

    if args.article_id:
        suffix = f"_{args.article_id}"
    else:
        suffix = ""

    summary_csv = (
        args.summary_csv
        or benchmark_root / f"selected50_curatability_summary{suffix}.csv"
    )
    component_csv = (
        args.component_csv
        or benchmark_root / f"selected50_curatability_component_scores{suffix}.csv"
    )
    issue_csv = (
        args.issue_csv
        or benchmark_root / f"selected50_curatability_issue_manifest{suffix}.csv"
    )

    write_manifest(summary_rows, summary_csv)
    write_manifest(component_rows, component_csv)
    write_manifest(issue_rows, issue_csv)

    print(f"Wrote curatability summary: {summary_csv}")
    print(f"Wrote component scores: {component_csv}")
    print(f"Wrote issue manifest: {issue_csv}")

    print("\nSummary")
    print("-------")
    print("articles:", len(summary_rows))

    if summary_rows:
        avg_overall = sum(
            safe_float(r.get("overall_score"))
            for r in summary_rows
        ) / len(summary_rows)

        avg_grounding = sum(
            safe_float(r.get("physical_grounding_score"))
            for r in summary_rows
        ) / len(summary_rows)

        avg_preview = sum(
            safe_float(r.get("executable_preview_score"))
            for r in summary_rows
        ) / len(summary_rows)

        print("avg overall_score:", round(avg_overall, 4))
        print("avg physical_grounding_score:", round(avg_grounding, 4))
        print("avg executable_preview_score:", round(avg_preview, 4))

        rec_counts = Counter(
            r.get("recommendation")
            for r in summary_rows
        )

        print("recommendations:")
        for key, value in rec_counts.most_common():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
