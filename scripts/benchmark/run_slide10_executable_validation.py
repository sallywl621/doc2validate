#!/usr/bin/env python3
from pathlib import Path
import csv
import json
import hashlib
import math
from collections import Counter

import pandas as pd


BENCHMARK_ROOT = Path("/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1")
OUT_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "validation_slide10"
TARGET_CSV = OUT_DIR / "slide10_validation_targets.csv"

FILE_EXECUTION_CSV = OUT_DIR / "slide10_validation_file_execution_manifest.csv"
COLUMN_EXECUTION_CSV = OUT_DIR / "slide10_validation_column_execution_manifest.csv"
PROFILE_JSONL = OUT_DIR / "slide10_validation_profiles.jsonl"
SUMMARY_JSON = OUT_DIR / "slide10_validation_execution_summary.json"
SUCCESS_EXAMPLES_CSV = OUT_DIR / "slide10_success_examples.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def as_int(x, default=0):
    try:
        if x is None or str(x).strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default


def safe_float(x):
    try:
        if pd.isna(x):
            return None
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def split_columns(text):
    if not text:
        return []
    return [x.strip() for x in str(text).split("|") if x.strip()]


def read_csv_safely(path: Path, **kwargs):
    if kwargs.get("engine") == "python":
        return pd.read_csv(path, **kwargs)
    return pd.read_csv(path, low_memory=False, **kwargs)


def load_dataframe(path: Path, suffix: str):
    suffix = suffix.lower().strip()

    if suffix == ".csv":
        attempts = [
            {"sep": ",", "encoding": "utf-8"},
            {"sep": None, "engine": "python", "encoding": "utf-8"},
            {"sep": ",", "encoding": "latin1"},
            {"sep": None, "engine": "python", "encoding": "latin1"},
        ]
        last_err = None
        for kwargs in attempts:
            try:
                return read_csv_safely(path, **kwargs)
            except Exception as e:
                last_err = e
        raise last_err

    if suffix == ".tsv":
        attempts = [
            {"sep": "\t", "encoding": "utf-8"},
            {"sep": "\t", "encoding": "latin1"},
        ]
        last_err = None
        for kwargs in attempts:
            try:
                return read_csv_safely(path, **kwargs)
            except Exception as e:
                last_err = e
        raise last_err

    if suffix == ".xlsx":
        return pd.read_excel(path)

    raise ValueError("Unsupported suffix for this experiment: " + suffix)

def normalize_col_name(x):
    return str(x).strip().lower()


def resolve_column(df, requested):
    """
    Return actual dataframe column name and match mode.
    """
    cols = list(df.columns)

    # exact
    for c in cols:
        if str(c) == requested:
            return c, "exact"

    # strip exact
    requested_strip = str(requested).strip()
    for c in cols:
        if str(c).strip() == requested_strip:
            return c, "strip"

    # case-insensitive normalized
    requested_norm = normalize_col_name(requested)
    for c in cols:
        if normalize_col_name(c) == requested_norm:
            return c, "casefold_strip"

    return None, "missing"


def sha256_series(series, max_values=None):
    """
    Ordered hash over normalized string representation.
    This is a reference signature for the current artifact snapshot.
    """
    h = hashlib.sha256()
    n = 0

    for v in series:
        if pd.isna(v):
            s = "<NA>"
        else:
            s = str(v).strip()

        h.update(s.encode("utf-8", errors="replace"))
        h.update(b"\n")
        n += 1

        if max_values is not None and n >= max_values:
            break

    return h.hexdigest()


def dtype_group(series):
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string_or_object"


def profile_column(series):
    group = dtype_group(series)

    profile = {
        "dtype": str(series.dtype),
        "dtype_group": group,
        "count": int(series.shape[0]),
        "null_count": int(series.isna().sum()),
        "non_null_count": int(series.notna().sum()),
    }

    if group == "numeric":
        numeric = pd.to_numeric(series, errors="coerce")
        profile.update({
            "numeric_count": int(numeric.notna().sum()),
            "numeric_null_or_parse_fail_count": int(numeric.isna().sum()),
            "min": safe_float(numeric.min()),
            "max": safe_float(numeric.max()),
            "sum": safe_float(numeric.sum()),
            "mean": safe_float(numeric.mean()),
            "std": safe_float(numeric.std()),
        })
    else:
        as_str = series.astype("string")
        profile.update({
            "unique_count": int(as_str.nunique(dropna=True)),
            "ordered_sha256": sha256_series(as_str),
            "sample_100_sha256": sha256_series(as_str, max_values=100),
        })

    return profile


targets = read_csv(TARGET_CSV)

file_rows = []
column_rows = []
profile_records = []

for idx, t in enumerate(targets, start=1):
    article_id = t.get("article_id")
    logical_file_id = t.get("logical_file_id")
    logical_name = t.get("logical_name")
    suffix = (t.get("observed_suffix") or "").lower().strip()
    path_text = t.get("resolved_physical_path") or ""
    path = Path(path_text)
    target_columns = split_columns(t.get("matched_columns"))

    file_key = f"{article_id}::{logical_file_id}"

    file_result = {
        "article_id": article_id,
        "logical_file_id": logical_file_id,
        "logical_name": logical_name,
        "observed_suffix": suffix,
        "resolved_physical_path": path_text,
        "target_columns": "|".join(target_columns),
        "num_target_columns": len(target_columns),
        "validation_job_generated": True,
        "load_success": False,
        "n_rows": "",
        "n_cols": "",
        "column_access_success_count": 0,
        "profile_success_count": 0,
        "execution_success": False,
        "failure_reason": "",
    }

    try:
        if not path.exists():
            raise FileNotFoundError(f"Resolved physical path does not exist: {path}")

        df = load_dataframe(path, suffix)

        file_result["load_success"] = True
        file_result["n_rows"] = int(df.shape[0])
        file_result["n_cols"] = int(df.shape[1])

        file_profile = {
            "article_id": article_id,
            "logical_file_id": logical_file_id,
            "logical_name": logical_name,
            "physical_path": path_text,
            "observed_suffix": suffix,
            "n_rows": int(df.shape[0]),
            "n_cols": int(df.shape[1]),
            "columns": [],
        }

        for requested_col in target_columns:
            actual_col, match_mode = resolve_column(df, requested_col)

            col_result = {
                "article_id": article_id,
                "logical_file_id": logical_file_id,
                "logical_name": logical_name,
                "physical_path": path_text,
                "requested_column": requested_col,
                "resolved_column": str(actual_col) if actual_col is not None else "",
                "column_access_success": actual_col is not None,
                "column_match_mode": match_mode,
                "profile_success": False,
                "dtype": "",
                "dtype_group": "",
                "failure_reason": "",
            }

            if actual_col is None:
                col_result["failure_reason"] = "matched_column_not_found_in_loaded_dataframe"
                column_rows.append(col_result)
                continue

            try:
                p = profile_column(df[actual_col])
                col_result["profile_success"] = True
                col_result["dtype"] = p["dtype"]
                col_result["dtype_group"] = p["dtype_group"]

                file_profile["columns"].append({
                    "requested_column": requested_col,
                    "resolved_column": str(actual_col),
                    "profile": p,
                })

            except Exception as e:
                col_result["failure_reason"] = f"profile_error: {type(e).__name__}: {e}"

            column_rows.append(col_result)

        file_result["column_access_success_count"] = sum(
            1 for r in column_rows
            if r["article_id"] == article_id
            and r["logical_file_id"] == logical_file_id
            and r["column_access_success"]
        )

        file_result["profile_success_count"] = sum(
            1 for r in column_rows
            if r["article_id"] == article_id
            and r["logical_file_id"] == logical_file_id
            and r["profile_success"]
        )

        file_result["execution_success"] = (
            file_result["load_success"]
            and file_result["num_target_columns"] > 0
            and file_result["profile_success_count"] == file_result["num_target_columns"]
        )

        profile_records.append(file_profile)

    except Exception as e:
        file_result["failure_reason"] = f"{type(e).__name__}: {e}"

    file_rows.append(file_result)


# Write outputs
file_fieldnames = [
    "article_id",
    "logical_file_id",
    "logical_name",
    "observed_suffix",
    "resolved_physical_path",
    "target_columns",
    "num_target_columns",
    "validation_job_generated",
    "load_success",
    "n_rows",
    "n_cols",
    "column_access_success_count",
    "profile_success_count",
    "execution_success",
    "failure_reason",
]

column_fieldnames = [
    "article_id",
    "logical_file_id",
    "logical_name",
    "physical_path",
    "requested_column",
    "resolved_column",
    "column_access_success",
    "column_match_mode",
    "profile_success",
    "dtype",
    "dtype_group",
    "failure_reason",
]

write_csv(FILE_EXECUTION_CSV, file_rows, file_fieldnames)
write_csv(COLUMN_EXECUTION_CSV, column_rows, column_fieldnames)

with PROFILE_JSONL.open("w", encoding="utf-8") as f:
    for rec in profile_records:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# Summary
num_files = len(file_rows)
num_generated = sum(1 for r in file_rows if r["validation_job_generated"])
num_load_success = sum(1 for r in file_rows if r["load_success"])
num_execution_success = sum(1 for r in file_rows if r["execution_success"])
num_column_targets = len(column_rows)
num_column_access_success = sum(1 for r in column_rows if r["column_access_success"])
num_profile_success = sum(1 for r in column_rows if r["profile_success"])

dtype_dist = Counter(r["dtype_group"] for r in column_rows if r["profile_success"])
file_failure_dist = Counter(r["failure_reason"] for r in file_rows if r["failure_reason"])
column_failure_dist = Counter(r["failure_reason"] for r in column_rows if r["failure_reason"])

summary = {
    "validation_candidate_files": num_files,
    "validation_jobs_generated": num_generated,
    "job_generation_success_rate": num_generated / num_files if num_files else None,
    "file_load_success": num_load_success,
    "file_load_success_rate": num_load_success / num_files if num_files else None,
    "file_execution_success": num_execution_success,
    "file_execution_success_rate": num_execution_success / num_files if num_files else None,
    "column_targets": num_column_targets,
    "column_access_success": num_column_access_success,
    "column_access_success_rate": num_column_access_success / num_column_targets if num_column_targets else None,
    "column_profile_success": num_profile_success,
    "column_profile_success_rate": num_profile_success / num_column_targets if num_column_targets else None,
    "dtype_group_distribution": dict(dtype_dist),
    "file_failure_distribution": dict(file_failure_dist),
    "column_failure_distribution": dict(column_failure_dist),
    "outputs": {
        "file_execution_manifest": str(FILE_EXECUTION_CSV),
        "column_execution_manifest": str(COLUMN_EXECUTION_CSV),
        "profile_jsonl": str(PROFILE_JSONL),
        "summary_json": str(SUMMARY_JSON),
    }
}

with SUMMARY_JSON.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)


# Success examples
success_examples = [
    r for r in file_rows
    if r["execution_success"]
]

success_examples = sorted(
    success_examples,
    key=lambda r: (as_int(r["profile_success_count"]), as_int(r["n_rows"])),
    reverse=True
)

write_csv(SUCCESS_EXAMPLES_CSV, success_examples[:20], file_fieldnames)

print(json.dumps(summary, indent=2, ensure_ascii=False))

print("\nTop successful examples:")
for r in success_examples[:10]:
    print(
        f"{r['article_id']} | {r['logical_file_id']} | {r['logical_name']} | "
        f"cols={r['profile_success_count']}/{r['num_target_columns']} | "
        f"rows={r['n_rows']} | suffix={r['observed_suffix']}"
    )

print("\nWrote:")
print(FILE_EXECUTION_CSV)
print(COLUMN_EXECUTION_CSV)
print(PROFILE_JSONL)
print(SUMMARY_JSON)
print(SUCCESS_EXAMPLES_CSV)
