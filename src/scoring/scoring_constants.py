from __future__ import annotations

SUPPORTED_TABULAR_FORMATS = {
    "csv",
    "tsv",
    "xlsx",
    "xls",
    "json",
    "jsonl",
    "parquet",
}

SCS_VERSION = "SCS_v4_run_based"

SCS_WEIGHTS = {
    "org_score": 20,
    "tabular_score": 25,
    "column_score": 20,
    "schema_score": 15,
    "path_score": 10,
    "repo_score": 10,
    "confidence_score": 10,
    "generation_score": 10,
}
