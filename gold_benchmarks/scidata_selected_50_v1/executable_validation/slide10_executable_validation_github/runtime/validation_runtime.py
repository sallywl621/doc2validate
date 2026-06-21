from pathlib import Path
import json
import hashlib
import math
import pandas as pd


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

    raise ValueError("Unsupported suffix: " + suffix)


def normalize_col_name(x):
    return str(x).strip().lower()


def resolve_column(df, requested):
    cols = list(df.columns)

    for c in cols:
        if str(c) == requested:
            return c, "exact"

    requested_strip = str(requested).strip()
    for c in cols:
        if str(c).strip() == requested_strip:
            return c, "strip"

    requested_norm = normalize_col_name(requested)
    for c in cols:
        if normalize_col_name(c) == requested_norm:
            return c, "casefold_strip"

    return None, "missing"


def sha256_series(series, max_values=None):
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


def run_validation(spec, benchmark_root):
    benchmark_root = Path(benchmark_root)
    artifact_path = benchmark_root / spec["artifact_relative_path"]

    result = {
        "article_id": spec["article_id"],
        "logical_file_id": spec["logical_file_id"],
        "logical_name": spec["logical_name"],
        "artifact_relative_path": spec["artifact_relative_path"],
        "observed_suffix": spec["observed_suffix"],
        "load_success": False,
        "n_rows": None,
        "n_cols": None,
        "columns": [],
        "failure_reason": "",
    }

    try:
        df = load_dataframe(artifact_path, spec["observed_suffix"])
        result["load_success"] = True
        result["n_rows"] = int(df.shape[0])
        result["n_cols"] = int(df.shape[1])

        for requested_col in spec["target_columns"]:
            actual_col, match_mode = resolve_column(df, requested_col)

            col_result = {
                "requested_column": requested_col,
                "resolved_column": str(actual_col) if actual_col is not None else "",
                "column_access_success": actual_col is not None,
                "column_match_mode": match_mode,
                "profile_success": False,
                "profile": None,
                "failure_reason": "",
            }

            if actual_col is None:
                col_result["failure_reason"] = "matched_column_not_found_in_loaded_dataframe"
                result["columns"].append(col_result)
                continue

            try:
                col_result["profile"] = profile_column(df[actual_col])
                col_result["profile_success"] = True
            except Exception as e:
                col_result["failure_reason"] = "profile_error: " + type(e).__name__ + ": " + str(e)

            result["columns"].append(col_result)

    except Exception as e:
        result["failure_reason"] = type(e).__name__ + ": " + str(e)

    return result
