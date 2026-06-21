import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_json(obj: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default

    try:
        if value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    try:
        if value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def pct(n: float, d: float) -> float:
    if d == 0:
        return 0.0

    return 100.0 * n / d


def pct_text(n: float, d: float, digits: int = 1) -> str:
    return f"{pct(n, d):.{digits}f}%"


def numeric_values(
    rows: Iterable[Dict[str, Any]],
    field: str,
) -> List[float]:
    values = []

    for row in rows:
        raw = row.get(field)

        if raw is None or raw == "":
            continue

        try:
            values.append(float(raw))
        except Exception:
            continue

    return values


def percentile(
    values: List[float],
    p: float,
) -> float:
    if not values:
        return 0.0

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    pos = (len(values) - 1) * p
    lower = int(pos)
    upper = min(lower + 1, len(values) - 1)
    weight = pos - lower

    return values[lower] * (1 - weight) + values[upper] * weight


def describe_numeric(
    rows: List[Dict[str, Any]],
    field: str,
) -> Dict[str, Any]:
    values = numeric_values(rows, field)

    if not values:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
        }

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = variance ** 0.5
    else:
        std = 0.0

    return {
        "count": n,
        "mean": mean,
        "std": std,
        "min": min(values),
        "p25": percentile(values, 0.25),
        "median": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "max": max(values),
    }


def mean_field(
    rows: List[Dict[str, Any]],
    field: str,
) -> float:
    values = numeric_values(rows, field)

    if not values:
        return 0.0

    return sum(values) / len(values)


def sum_field(
    rows: List[Dict[str, Any]],
    field: str,
) -> int:
    return sum(safe_int(row.get(field)) for row in rows)


def count_by_field(
    rows: List[Dict[str, Any]],
    field: str,
) -> Dict[str, int]:
    c = Counter()

    for row in rows:
        key = str(row.get(field) or "").strip()

        if not key:
            key = "missing"

        c[key] += 1

    return dict(c)


def group_sum(
    rows: List[Dict[str, Any]],
    key_fields: Tuple[str, ...],
    value_field: str,
) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, ...], int] = defaultdict(int)

    for row in rows:
        key = tuple(str(row.get(k) or "") for k in key_fields)
        groups[key] += safe_int(row.get(value_field))

    out = []

    for key, value in groups.items():
        r = {
            field: key[i]
            for i, field in enumerate(key_fields)
        }
        r["count"] = value
        out.append(r)

    out.sort(key=lambda x: x["count"], reverse=True)

    return out


def top_cases(
    summary_rows: List[Dict[str, Any]],
    field: str,
    n: int,
    reverse: bool,
) -> List[Dict[str, Any]]:
    rows = list(summary_rows)

    rows.sort(
        key=lambda r: safe_float(r.get(field)),
        reverse=reverse,
    )

    keep_fields = [
        "article_id",
        "overall_score",
        "recommendation",
        "physical_grounding_score",
        "executable_preview_score",
        "review_burden_score",
        "num_missing",
        "num_ambiguous",
        "num_human_review_needed",
    ]

    return [
        {
            f: r.get(f)
            for f in keep_fields
        }
        for r in rows[:n]
    ]


def round_nested(obj: Any, digits: int = 4) -> Any:
    if isinstance(obj, dict):
        return {
            k: round_nested(v, digits=digits)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [
            round_nested(v, digits=digits)
            for v in obj
        ]

    if isinstance(obj, float):
        return round(obj, digits)

    return obj


def format_number(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""

    if isinstance(value, float):
        return f"{value:.{digits}f}"

    try:
        f = float(value)
        return f"{f:.{digits}f}"
    except Exception:
        return str(value)


def markdown_table(
    rows: List[Dict[str, Any]],
    columns: List[str],
    headers: List[str] | None = None,
    max_rows: int | None = None,
) -> str:
    if headers is None:
        headers = columns

    if max_rows is not None:
        rows = rows[:max_rows]

    lines = []

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for row in rows:
        values = []

        for col in columns:
            value = row.get(col, "")

            if isinstance(value, float):
                value = f"{value:.4f}"

            values.append(str(value))

        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def make_component_means(
    summary_rows: List[Dict[str, Any]],
) -> Dict[str, float]:
    fields = [
        "logical_schema_score",
        "physical_grounding_score",
        "executable_preview_score",
        "review_burden_score",
        "intervention_need_score",
        "overall_score",
    ]

    return {
        field: mean_field(summary_rows, field)
        for field in fields
    }


def make_preview_outcome_counts(
    preview_rows: List[Dict[str, Any]],
) -> Dict[str, int]:
    if not preview_rows:
        return {}

    return count_by_field(preview_rows, "preview_outcome_category")


def make_execution_status_counts(
    execution_rows: List[Dict[str, Any]],
) -> Dict[str, int]:
    if not execution_rows:
        return {}

    return count_by_field(execution_rows, "status")


def make_report(
    benchmark_root: Path,
    summary_rows: List[Dict[str, Any]],
    component_rows: List[Dict[str, Any]],
    issue_rows: List[Dict[str, Any]],
    execution_rows: List[Dict[str, Any]],
    preview_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    n_articles = len(summary_rows)

    recommendation_counts = count_by_field(summary_rows, "recommendation")
    component_means = make_component_means(summary_rows)
    overall_distribution = describe_numeric(summary_rows, "overall_score")

    issue_totals = group_sum(
        issue_rows,
        key_fields=("issue_scope", "issue_type"),
        value_field="count",
    )

    preview_outcome_counts = make_preview_outcome_counts(preview_rows)
    execution_status_counts = make_execution_status_counts(execution_rows)

    total_preview_rows = len(preview_rows)
    tabular_preview_success = preview_outcome_counts.get(
        "tabular_preview_success",
        0,
    )
    preview_non_success = total_preview_rows - tabular_preview_success

    total_human_review_needed = sum_field(
        summary_rows,
        "num_human_review_needed",
    )
    total_missing = sum_field(summary_rows, "num_missing")
    total_ambiguous = sum_field(summary_rows, "num_ambiguous")
    total_weak = sum_field(summary_rows, "num_weak_match")

    total_logical_files = sum_field(summary_rows, "num_logical_files")
    total_file_grounding_applicable = sum_field(
        summary_rows,
        "num_file_grounding_applicable",
    )

    total_resolved = sum_field(summary_rows, "num_resolved")

    lowest_cases = top_cases(
        summary_rows,
        field="overall_score",
        n=10,
        reverse=False,
    )

    highest_cases = top_cases(
        summary_rows,
        field="overall_score",
        n=10,
        reverse=True,
    )

    accepted_light = recommendation_counts.get(
        "accept_for_ingest_with_light_review",
        0,
    )
    accepted_curator = recommendation_counts.get(
        "accept_with_curator_review",
        0,
    )
    request_supp = recommendation_counts.get(
        "request_supplementary_materials_or_manual_mapping",
        0,
    )
    high_risk = recommendation_counts.get(
        "high_risk_manual_review",
        0,
    )

    slide_ready_findings = [
        (
            f"Across {n_articles} selected benchmark cases, the mean overall "
            f"curatability score was {component_means.get('overall_score', 0):.3f}."
        ),
        (
            f"Logical schema completeness was high on average "
            f"({component_means.get('logical_schema_score', 0):.3f}), but "
            f"physical grounding was substantially lower "
            f"({component_means.get('physical_grounding_score', 0):.3f}), "
            f"indicating that documentation-derived schema completeness does "
            f"not imply physical curatability."
        ),
        (
            f"The system resolved {total_resolved} of "
            f"{total_file_grounding_applicable} file-grounding-applicable "
            f"logical claims "
            f"({pct_text(total_resolved, total_file_grounding_applicable)})."
        ),
        (
            f"Human review was requested for {total_human_review_needed} "
            f"logical file claims, reflecting curator workload that remains "
            f"after automated grounding and preview."
        ),
        (
            f"All generated notebooks that were executed completed successfully "
            f"({execution_status_counts.get('success', 0)} / {n_articles}), "
            f"while artifact preview exposed heterogeneous artifact-level "
            f"inspection needs."
        ),
        (
            f"The generic preview helper successfully loaded "
            f"{tabular_preview_success} of {total_preview_rows} preview targets "
            f"({pct_text(tabular_preview_success, total_preview_rows)}). The "
            f"remaining {preview_non_success} targets required non-generic "
            f"handling such as archive unpacking, specialized loaders, text/code "
            f"inspection, or encoding repair."
        ),
        (
            f"Recommendation distribution: {accepted_light} light-review ingest, "
            f"{accepted_curator} curator-review ingest, {request_supp} request "
            f"supplementary materials/manual mapping, and {high_risk} high-risk "
            f"manual review."
        ),
    ]

    report = {
        "created_at": datetime.now().isoformat(),
        "benchmark_root": str(benchmark_root),
        "n_articles": n_articles,
        "score_distribution": {
            "overall_score": overall_distribution,
        },
        "component_means": component_means,
        "recommendation_counts": recommendation_counts,
        "execution_status_counts": execution_status_counts,
        "grounding_totals": {
            "total_logical_files": total_logical_files,
            "total_file_grounding_applicable": total_file_grounding_applicable,
            "total_resolved": total_resolved,
            "total_ambiguous": total_ambiguous,
            "total_weak_match": total_weak,
            "total_missing": total_missing,
            "total_human_review_needed": total_human_review_needed,
            "resolved_rate": (
                total_resolved / total_file_grounding_applicable
                if total_file_grounding_applicable
                else 0.0
            ),
        },
        "preview_totals": {
            "total_preview_rows": total_preview_rows,
            "tabular_preview_success": tabular_preview_success,
            "preview_non_success": preview_non_success,
            "tabular_preview_success_rate": (
                tabular_preview_success / total_preview_rows
                if total_preview_rows
                else 0.0
            ),
            "preview_outcome_counts": preview_outcome_counts,
        },
        "issue_totals": issue_totals,
        "lowest_overall_score_cases": lowest_cases,
        "highest_overall_score_cases": highest_cases,
        "slide_ready_findings": slide_ready_findings,
    }

    return round_nested(report)


def make_markdown_report(
    report: Dict[str, Any],
) -> str:
    n_articles = report["n_articles"]

    component_means = report["component_means"]
    recommendation_counts = report["recommendation_counts"]
    grounding_totals = report["grounding_totals"]
    preview_totals = report["preview_totals"]
    issue_totals = report["issue_totals"]
    score_dist = report["score_distribution"]["overall_score"]

    lines = []

    lines.append("# Selected-50 Curatability Aggregate Report")
    lines.append("")
    lines.append(f"Created at: `{report['created_at']}`")
    lines.append("")
    lines.append("## Key numbers")
    lines.append("")

    key_rows = [
        {
            "metric": "Articles",
            "value": n_articles,
        },
        {
            "metric": "Mean overall score",
            "value": format_number(component_means.get("overall_score")),
        },
        {
            "metric": "Mean logical schema score",
            "value": format_number(component_means.get("logical_schema_score")),
        },
        {
            "metric": "Mean physical grounding score",
            "value": format_number(component_means.get("physical_grounding_score")),
        },
        {
            "metric": "Mean executable preview score",
            "value": format_number(component_means.get("executable_preview_score")),
        },
        {
            "metric": "Mean review burden score",
            "value": format_number(component_means.get("review_burden_score")),
        },
        {
            "metric": "Mean intervention need score",
            "value": format_number(component_means.get("intervention_need_score")),
        },
        {
            "metric": "Resolved grounding claims",
            "value": (
                f"{grounding_totals.get('total_resolved')} / "
                f"{grounding_totals.get('total_file_grounding_applicable')} "
                f"({pct_text(grounding_totals.get('total_resolved', 0), grounding_totals.get('total_file_grounding_applicable', 0))})"
            ),
        },
        {
            "metric": "Human review targets",
            "value": grounding_totals.get("total_human_review_needed"),
        },
        {
            "metric": "Tabular preview success",
            "value": (
                f"{preview_totals.get('tabular_preview_success')} / "
                f"{preview_totals.get('total_preview_rows')} "
                f"({pct_text(preview_totals.get('tabular_preview_success', 0), preview_totals.get('total_preview_rows', 0))})"
            ),
        },
    ]

    lines.append(markdown_table(key_rows, ["metric", "value"], ["Metric", "Value"]))
    lines.append("")

    lines.append("## Overall score distribution")
    lines.append("")

    score_rows = [
        {
            "stat": "count",
            "value": score_dist.get("count"),
        },
        {
            "stat": "mean",
            "value": format_number(score_dist.get("mean")),
        },
        {
            "stat": "std",
            "value": format_number(score_dist.get("std")),
        },
        {
            "stat": "min",
            "value": format_number(score_dist.get("min")),
        },
        {
            "stat": "p25",
            "value": format_number(score_dist.get("p25")),
        },
        {
            "stat": "median",
            "value": format_number(score_dist.get("median")),
        },
        {
            "stat": "p75",
            "value": format_number(score_dist.get("p75")),
        },
        {
            "stat": "max",
            "value": format_number(score_dist.get("max")),
        },
    ]

    lines.append(markdown_table(score_rows, ["stat", "value"], ["Statistic", "Value"]))
    lines.append("")

    lines.append("## Recommendation counts")
    lines.append("")

    rec_rows = []

    for key, value in sorted(
        recommendation_counts.items(),
        key=lambda kv: kv[1],
        reverse=True,
    ):
        rec_rows.append(
            {
                "recommendation": key,
                "count": value,
                "percent": pct_text(value, n_articles),
            }
        )

    lines.append(
        markdown_table(
            rec_rows,
            ["recommendation", "count", "percent"],
            ["Recommendation", "Count", "Percent"],
        )
    )
    lines.append("")

    lines.append("## Component means")
    lines.append("")

    comp_rows = []

    for key, value in sorted(
        component_means.items(),
        key=lambda kv: kv[1],
        reverse=True,
    ):
        comp_rows.append(
            {
                "component": key,
                "mean": format_number(value),
            }
        )

    lines.append(
        markdown_table(
            comp_rows,
            ["component", "mean"],
            ["Component", "Mean"],
        )
    )
    lines.append("")

    lines.append("## Top issues")
    lines.append("")

    lines.append(
        markdown_table(
            issue_totals,
            ["issue_scope", "issue_type", "count"],
            ["Scope", "Issue type", "Count"],
            max_rows=20,
        )
    )
    lines.append("")

    lines.append("## Preview outcome counts")
    lines.append("")

    preview_rows = []

    for key, value in sorted(
        preview_totals.get("preview_outcome_counts", {}).items(),
        key=lambda kv: kv[1],
        reverse=True,
    ):
        preview_rows.append(
            {
                "preview_outcome": key,
                "count": value,
                "percent": pct_text(value, preview_totals.get("total_preview_rows", 0)),
            }
        )

    lines.append(
        markdown_table(
            preview_rows,
            ["preview_outcome", "count", "percent"],
            ["Preview outcome", "Count", "Percent"],
        )
    )
    lines.append("")

    lines.append("## Lowest overall-score cases")
    lines.append("")

    lines.append(
        markdown_table(
            report["lowest_overall_score_cases"],
            [
                "article_id",
                "overall_score",
                "recommendation",
                "physical_grounding_score",
                "executable_preview_score",
                "review_burden_score",
                "num_missing",
                "num_ambiguous",
                "num_human_review_needed",
            ],
            [
                "Article ID",
                "Overall",
                "Recommendation",
                "Grounding",
                "Preview",
                "Review burden",
                "Missing",
                "Ambiguous",
                "Review targets",
            ],
        )
    )
    lines.append("")

    lines.append("## Highest overall-score cases")
    lines.append("")

    lines.append(
        markdown_table(
            report["highest_overall_score_cases"],
            [
                "article_id",
                "overall_score",
                "recommendation",
                "physical_grounding_score",
                "executable_preview_score",
                "review_burden_score",
                "num_missing",
                "num_ambiguous",
                "num_human_review_needed",
            ],
            [
                "Article ID",
                "Overall",
                "Recommendation",
                "Grounding",
                "Preview",
                "Review burden",
                "Missing",
                "Ambiguous",
                "Review targets",
            ],
        )
    )
    lines.append("")

    lines.append("## Slide-ready findings")
    lines.append("")

    for finding in report["slide_ready_findings"]:
        lines.append(f"- {finding}")

    lines.append("")

    lines.append("## Suggested paper wording")
    lines.append("")
    lines.append(
        "Documentation-derived schema completeness did not imply curatability. "
        "Although selected benchmark cases had high logical-schema scores, "
        "physical grounding, executable preview, and review-burden signals "
        "revealed substantial downstream curator workload. These results support "
        "treating curatability as a measurable, evidence-grounded property of "
        "dataset deposits rather than as a property of documentation alone."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--benchmark-root",
        type=Path,
        required=True,
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
        "--execution-manifest",
        type=Path,
    )

    parser.add_argument(
        "--preview-manifest",
        type=Path,
    )

    parser.add_argument(
        "--output-json",
        type=Path,
    )

    parser.add_argument(
        "--output-md",
        type=Path,
    )

    args = parser.parse_args()

    benchmark_root = args.benchmark_root.resolve()

    summary_csv = (
        args.summary_csv
        or benchmark_root / "selected50_curatability_summary.csv"
    )
    component_csv = (
        args.component_csv
        or benchmark_root / "selected50_curatability_component_scores.csv"
    )
    issue_csv = (
        args.issue_csv
        or benchmark_root / "selected50_curatability_issue_manifest.csv"
    )
    execution_manifest = (
        args.execution_manifest
        or benchmark_root / "curatability_notebook_execution_manifest.csv"
    )
    preview_manifest = (
        args.preview_manifest
        or benchmark_root / "curatability_notebook_preview_manifest_classified.csv"
    )

    output_json = (
        args.output_json
        or benchmark_root / "selected50_curatability_aggregate_report.json"
    )
    output_md = (
        args.output_md
        or benchmark_root / "selected50_curatability_slide_stats.md"
    )

    summary_rows = read_csv_rows(summary_csv)
    component_rows = read_csv_rows(component_csv)
    issue_rows = read_csv_rows(issue_csv)
    execution_rows = read_csv_rows(execution_manifest)
    preview_rows = read_csv_rows(preview_manifest)

    report = make_report(
        benchmark_root=benchmark_root,
        summary_rows=summary_rows,
        component_rows=component_rows,
        issue_rows=issue_rows,
        execution_rows=execution_rows,
        preview_rows=preview_rows,
    )

    markdown = make_markdown_report(report)

    write_json(report, output_json)
    write_text(markdown, output_md)

    print(f"Wrote aggregate JSON report: {output_json}")
    print(f"Wrote slide-ready markdown: {output_md}")

    print("\nSummary")
    print("-------")
    print("articles:", report["n_articles"])
    print("mean overall_score:", report["score_distribution"]["overall_score"]["mean"])
    print("recommendation counts:")
    for key, value in report["recommendation_counts"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
