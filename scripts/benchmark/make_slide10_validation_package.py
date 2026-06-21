from pathlib import Path
import csv
import json
import re
import shutil

BENCHMARK_ROOT = Path("/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1")
VAL_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "validation_slide10"
TARGET_CSV = VAL_DIR / "slide10_validation_targets.csv"

PKG_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "slide10_executable_validation_github"

RUNTIME_DIR = PKG_DIR / "runtime"
SPECS_DIR = PKG_DIR / "specs"
VALIDATORS_DIR = PKG_DIR / "generated_validators"
RESULTS_DIR = PKG_DIR / "results"

for d in [RUNTIME_DIR, SPECS_DIR, VALIDATORS_DIR, RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def safe_name(x):
    x = str(x or "")
    x = x.strip()
    x = re.sub(r"[^A-Za-z0-9._-]+", "_", x)
    x = re.sub(r"_+", "_", x)
    return x.strip("_") or "unnamed"


def split_columns(text):
    if not text:
        return []
    return [x.strip() for x in str(text).split("|") if x.strip()]


def relative_to_benchmark(path_text):
    p = Path(path_text)
    try:
        return str(p.relative_to(BENCHMARK_ROOT))
    except Exception:
        return str(p)


RUNTIME_CODE = r'''from pathlib import Path
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
'''

RUNNER_CODE = r'''import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True)
    parser.add_argument("--out-dir", default="rerun_outputs")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    validators = sorted((root / "generated_validators").glob("*.py"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failed = 0

    for v in validators:
        out_json = out_dir / (v.stem + ".json")
        cmd = [
            sys.executable,
            str(v),
            "--benchmark-root",
            args.benchmark_root,
            "--out-json",
            str(out_json),
        ]
        r = subprocess.run(cmd)
        if r.returncode == 0:
            ok += 1
        else:
            failed += 1

    summary = {
        "validators": len(validators),
        "success": ok,
        "failed": failed,
        "out_dir": str(out_dir),
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
'''


VALIDATOR_TEMPLATE = r'''import argparse
import json
from pathlib import Path
from runtime.validation_runtime import run_validation


SPEC = __SPEC_JSON__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True)
    parser.add_argument("--out-json", default=None)
    args = parser.parse_args()

    result = run_validation(SPEC, args.benchmark_root)

    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))

    if not result.get("load_success"):
        raise SystemExit(2)

    columns = result.get("columns", [])
    if not columns:
        raise SystemExit(3)

    if not all(c.get("profile_success") for c in columns):
        raise SystemExit(4)


if __name__ == "__main__":
    main()
'''


README = r'''# Slide 10 Executable Validation Package

This package contains generated validation scripts for the Slide 10 experiment.

It does not include raw dataset artifacts.

## Contents

- runtime/validation_runtime.py
  Shared loader and profiling runtime.

- specs/
  One JSON validation specification per validation-ready logical file.

- generated_validators/
  One executable Python validator per validation-ready logical file.

- results/
  Execution manifests and profile signatures produced during the experiment.

- run_all_validators.py
  Convenience runner for re-executing all validators.

## Re-run

From this directory:

python run_all_validators.py --benchmark-root /path/to/scidata_selected_50_v1 --out-dir rerun_outputs

Each validator expects the original artifact tree to exist under benchmark root.

## What is validated

Each validator:

1. loads the resolved physical file
2. checks automatically matched columns
3. infers column data types
4. computes numeric summaries or string hash signatures

These scripts validate artifact integrity, schema consistency, and documented column availability.
They do not validate scientific correctness.
'''


REQUIREMENTS = r'''pandas
openpyxl
'''


# Write package files
(RUNTIME_DIR / "validation_runtime.py").write_text(RUNTIME_CODE, encoding="utf-8")
(PKG_DIR / "run_all_validators.py").write_text(RUNNER_CODE, encoding="utf-8")
(PKG_DIR / "README.md").write_text(README, encoding="utf-8")
(PKG_DIR / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
(RUNTIME_DIR / "__init__.py").write_text("", encoding="utf-8")

targets = read_csv(TARGET_CSV)

generated = []

for t in targets:
    article_id = t.get("article_id")
    logical_file_id = t.get("logical_file_id")
    logical_name = t.get("logical_name")
    suffix = t.get("observed_suffix")
    path_text = t.get("resolved_physical_path")
    cols = split_columns(t.get("matched_columns"))

    if not path_text or not cols:
        continue

    base = safe_name(article_id) + "__" + safe_name(logical_file_id) + "__" + safe_name(logical_name)
    spec_name = base + ".json"
    validator_name = base + ".py"

    spec = {
        "article_id": article_id,
        "logical_file_id": logical_file_id,
        "logical_name": logical_name,
        "observed_suffix": suffix,
        "artifact_relative_path": relative_to_benchmark(path_text),
        "target_columns": cols,
    }

    spec_path = SPECS_DIR / spec_name
    validator_path = VALIDATORS_DIR / validator_name

    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    validator_code = VALIDATOR_TEMPLATE.replace(
        "__SPEC_JSON__",
        json.dumps(spec, indent=2)
    )
    validator_path.write_text(validator_code, encoding="utf-8")

    generated.append({
        "article_id": article_id,
        "logical_file_id": logical_file_id,
        "logical_name": logical_name,
        "spec": str(spec_path.relative_to(PKG_DIR)),
        "validator": str(validator_path.relative_to(PKG_DIR)),
        "target_columns": len(cols),
    })


# Copy existing results
result_files = [
    "slide10_validation_execution_summary.json",
    "slide10_validation_file_execution_manifest.csv",
    "slide10_validation_column_execution_manifest.csv",
    "slide10_success_examples.csv",
    "slide10_validation_profiles.jsonl",
]

for name in result_files:
    src = VAL_DIR / name
    if src.exists():
        shutil.copy2(src, RESULTS_DIR / name)


# Write validator manifest
manifest_path = PKG_DIR / "generated_validator_manifest.csv"
with manifest_path.open("w", encoding="utf-8", newline="") as f:
    fieldnames = ["article_id", "logical_file_id", "logical_name", "spec", "validator", "target_columns"]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(generated)


print("package_dir:", PKG_DIR)
print("validators_generated:", len(generated))
print("validator_manifest:", manifest_path)
print("results_dir:", RESULTS_DIR)
