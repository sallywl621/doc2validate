from pathlib import Path
import csv
import json
from collections import defaultdict

BENCHMARK_ROOT = Path("/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1")
MANIFEST_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "manifests"
VAL_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "validation_slide10"
OUT_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "validation_slide12_score_alignment"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ARTICLE_MANIFEST = MANIFEST_DIR / "presentation_grounding_v2_article_manifest.csv"
FILE_EXEC = VAL_DIR / "slide10_validation_file_execution_manifest.csv"
COLUMN_EXEC = VAL_DIR / "slide10_validation_column_execution_manifest.csv"

OUT_ARTICLE = OUT_DIR / "slide12_score_alignment_by_article.csv"
OUT_BIN = OUT_DIR / "slide12_score_bin_summary.csv"
OUT_JSON = OUT_DIR / "slide12_score_alignment_summary.json"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def to_float(x, default=0.0):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except Exception:
        return default


def to_int(x, default=0):
    try:
        if x is None or str(x).strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default


def is_true(x):
    return str(x).strip().lower() in ["true", "1", "yes", "y"]


def score_bin(score):
    if score >= 0.65:
        return "high_score"
    if score >= 0.45:
        return "medium_score"
    return "low_score"


articles = read_csv(ARTICLE_MANIFEST)
file_exec = read_csv(FILE_EXEC)
col_exec = read_csv(COLUMN_EXEC)

file_by_article = defaultdict(lambda: {
    "validation_candidate_files": 0,
    "file_load_success": 0,
    "file_execution_success": 0,
})

for r in file_exec:
    aid = r.get("article_id")
    file_by_article[aid]["validation_candidate_files"] += 1
    if is_true(r.get("load_success")):
        file_by_article[aid]["file_load_success"] += 1
    if is_true(r.get("execution_success")):
        file_by_article[aid]["file_execution_success"] += 1

col_by_article = defaultdict(lambda: {
    "column_targets": 0,
    "column_access_success": 0,
    "column_profile_success": 0,
})

for r in col_exec:
    aid = r.get("article_id")
    col_by_article[aid]["column_targets"] += 1
    if is_true(r.get("column_access_success")):
        col_by_article[aid]["column_access_success"] += 1
    if is_true(r.get("profile_success")):
        col_by_article[aid]["column_profile_success"] += 1

article_rows = []

for a in articles:
    aid = a.get("article_id")
    score = to_float(a.get("presentation_grounding_score"))
    bin_name = score_bin(score)

    f = file_by_article[aid]
    c = col_by_article[aid]

    validation_candidate_files = f["validation_candidate_files"]
    file_load_success = f["file_load_success"]
    file_execution_success = f["file_execution_success"]

    column_targets = c["column_targets"]
    column_access_success = c["column_access_success"]
    column_profile_success = c["column_profile_success"]

    row = {
        "article_id": aid,
        "score_bin": bin_name,
        "presentation_grounding_score": score,
        "identity_grounding_score": to_float(a.get("identity_grounding_score")),
        "overall_column_coverage": to_float(a.get("overall_column_coverage"), default=""),
        "num_human_review_needed": to_int(a.get("num_human_review_needed")),
        "num_logical_files": to_int(a.get("num_logical_files")),
        "identity_status_resolved": to_int(a.get("identity_status_resolved")),
        "identity_status_ambiguous": to_int(a.get("identity_status_ambiguous")),
        "identity_status_missing": to_int(a.get("identity_status_missing")),
        "identity_status_weak_match": to_int(a.get("identity_status_weak_match")),
        "total_matched_columns": to_int(a.get("total_matched_columns")),
        "validation_candidate_files": validation_candidate_files,
        "file_load_success": file_load_success,
        "file_execution_success": file_execution_success,
        "file_execution_success_rate": (
            file_execution_success / validation_candidate_files
            if validation_candidate_files else ""
        ),
        "column_targets": column_targets,
        "column_access_success": column_access_success,
        "column_profile_success": column_profile_success,
        "column_profile_success_rate": (
            column_profile_success / column_targets
            if column_targets else ""
        ),
    }

    article_rows.append(row)


article_fieldnames = [
    "article_id",
    "score_bin",
    "presentation_grounding_score",
    "identity_grounding_score",
    "overall_column_coverage",
    "num_human_review_needed",
    "num_logical_files",
    "identity_status_resolved",
    "identity_status_ambiguous",
    "identity_status_missing",
    "identity_status_weak_match",
    "total_matched_columns",
    "validation_candidate_files",
    "file_load_success",
    "file_execution_success",
    "file_execution_success_rate",
    "column_targets",
    "column_access_success",
    "column_profile_success",
    "column_profile_success_rate",
]

write_csv(OUT_ARTICLE, article_rows, article_fieldnames)


# Bin summary
bins = defaultdict(list)
for r in article_rows:
    bins[r["score_bin"]].append(r)

bin_order = ["high_score", "medium_score", "low_score"]
bin_rows = []

for b in bin_order:
    rows = bins.get(b, [])
    n = len(rows)

    def avg(key):
        vals = []
        for r in rows:
            v = r.get(key)
            if v == "":
                continue
            vals.append(to_float(v))
        return sum(vals) / len(vals) if vals else ""

    def total(key):
        return sum(to_float(r.get(key)) for r in rows if r.get(key) != "")

    val_files = total("validation_candidate_files")
    exec_success = total("file_execution_success")
    col_targets = total("column_targets")
    col_profiles = total("column_profile_success")

    bin_rows.append({
        "score_bin": b,
        "n_articles": n,
        "avg_presentation_grounding_score": avg("presentation_grounding_score"),
        "avg_num_human_review_needed": avg("num_human_review_needed"),
        "avg_total_matched_columns": avg("total_matched_columns"),
        "total_validation_candidate_files": int(val_files),
        "total_file_execution_success": int(exec_success),
        "file_execution_success_rate": exec_success / val_files if val_files else "",
        "total_column_targets": int(col_targets),
        "total_column_profile_success": int(col_profiles),
        "column_profile_success_rate": col_profiles / col_targets if col_targets else "",
    })

bin_fieldnames = [
    "score_bin",
    "n_articles",
    "avg_presentation_grounding_score",
    "avg_num_human_review_needed",
    "avg_total_matched_columns",
    "total_validation_candidate_files",
    "total_file_execution_success",
    "file_execution_success_rate",
    "total_column_targets",
    "total_column_profile_success",
    "column_profile_success_rate",
]

write_csv(OUT_BIN, bin_rows, bin_fieldnames)


# Select example articles
high_examples = sorted(
    [r for r in article_rows if r["score_bin"] == "high_score"],
    key=lambda x: (
        to_float(x["presentation_grounding_score"]),
        to_int(x["file_execution_success"]),
        to_int(x["column_profile_success"])
    ),
    reverse=True
)[:5]

low_examples = sorted(
    [r for r in article_rows if r["score_bin"] == "low_score"],
    key=lambda x: (
        to_int(x["num_human_review_needed"]),
        to_int(x["identity_status_missing"]) + to_int(x["identity_status_ambiguous"]) + to_int(x["identity_status_weak_match"])
    ),
    reverse=True
)[:5]

summary = {
    "outputs": {
        "article_alignment_csv": str(OUT_ARTICLE),
        "score_bin_summary_csv": str(OUT_BIN),
        "summary_json": str(OUT_JSON),
    },
    "score_bins": bin_rows,
    "high_score_examples": high_examples,
    "low_score_review_burden_examples": low_examples,
}

OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print(json.dumps(summary, indent=2))
