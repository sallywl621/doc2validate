from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


SUPPORTED_FORMATS = {
    "csv",
    "tsv",
    "xlsx",
    "xls",
    "json",
    "jsonl",
    "parquet",
}


FORMAT_ALIASES = {
    "excel": "xlsx",
    "spreadsheet": "xlsx",
    "tab-separated": "tsv",
    "tab separated": "tsv",
    "comma-separated": "csv",
    "comma separated": "csv",
}


@dataclass
class SelectedFile:
    logical_name: str
    role: str
    format: str
    schema_type: str
    path: Optional[str]
    file_pattern: Optional[str]
    source: Optional[str]
    score: float
    expected_columns: Optional[List[str]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def norm_fmt(value: Any) -> str:
    if value is None:
        return "unknown"

    fmt = str(value).strip().lower()
    fmt = fmt.lstrip(".")
    fmt = FORMAT_ALIASES.get(fmt, fmt)

    if fmt in {"hdf", "hdf5"}:
        return "hdf5"

    return fmt or "unknown"


def safe_relpath(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in {"unknown", "null", "none", "n/a"}:
        return None

    # Keep comma-separated logical patterns as-is; they are handled by fallback search.
    if "," in text:
        return text

    path = Path(text)

    # Avoid writing absolute paths inferred by the model into generated manifests.
    if path.is_absolute():
        return path.name

    # Prevent parent traversal in generated loaders.
    clean_parts = [p for p in path.parts if p not in {"..", "."}]
    return str(Path(*clean_parts)) if clean_parts else None


def extract_expected_columns(file_obj: Dict[str, Any]) -> Optional[List[str]]:
    structure = file_obj.get("structure") or {}
    columns = structure.get("columns")

    if isinstance(columns, dict) and columns:
        return [str(k) for k in columns.keys()]

    if isinstance(columns, list) and columns:
        return [str(x) for x in columns]

    return None


def score_file(file_obj: Dict[str, Any]) -> float:
    fmt = norm_fmt(file_obj.get("format"))
    role = str(file_obj.get("role") or "unknown").strip().lower()
    schema_type = str(file_obj.get("schema_type") or "unknown").strip().lower()
    path = safe_relpath(file_obj.get("path") or "")
    file_pattern = safe_relpath(file_obj.get("file_pattern") or "")

    score = 0.0

    if role == "primary_data":
        score += 5.0
    elif role == "derived_data":
        score += 2.0
    elif role in {"metadata", "annotation"}:
        score += 0.5

    if schema_type == "tabular":
        score += 4.0
    elif schema_type == "hierarchical":
        score += 1.0
    elif schema_type == "text":
        score += 0.5

    if fmt in SUPPORTED_FORMATS:
        score += 4.0
    elif fmt == "unknown":
        score -= 0.5
    else:
        score -= 3.0

    if path:
        score += 1.5
    elif file_pattern:
        score += 1.0
    else:
        score -= 2.0

    expected_columns = extract_expected_columns(file_obj)
    if expected_columns:
        score += min(len(expected_columns), 5) * 0.2

    return score


def select_primary_files(
    files: List[Dict[str, Any]],
    top_k: int = 3,
) -> List[SelectedFile]:
    candidates: List[SelectedFile] = []

    for f in files:
        if not isinstance(f, dict):
            continue

        fmt = norm_fmt(f.get("format"))

        if fmt not in SUPPORTED_FORMATS:
            continue

        candidates.append(
            SelectedFile(
                logical_name=str(f.get("logical_name") or "unknown"),
                role=str(f.get("role") or "unknown"),
                format=fmt,
                schema_type=str(f.get("schema_type") or "unknown"),
                path=safe_relpath(f.get("path") or ""),
                file_pattern=safe_relpath(f.get("file_pattern") or ""),
                source=str(f.get("source") or ""),
                score=score_file(f),
                expected_columns=extract_expected_columns(f),
            )
        )

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:top_k]
