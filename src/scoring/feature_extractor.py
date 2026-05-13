from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from src.scoring.scoring_constants import SUPPORTED_TABULAR_FORMATS


def load_json(path: Path) -> Dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def normalize_format(fmt: str | None) -> str:
    if not fmt:
        return "unknown"

    fmt = str(fmt).strip().lower()

    aliases = {
        "excel": "xlsx",
        "netcdf": "netcdf",
        "hdf": "hdf5",
        "h5": "hdf5",
    }

    return aliases.get(fmt, fmt)


def infer_path_accessibility(files: list[dict]) -> Tuple[int, int]:
    n_known = 0
    n_pattern = 0

    for f in files:
        path = (f.get("path") or "").strip()
        pattern = (f.get("file_pattern") or "").strip()

        if path and path != "unknown":
            n_known += 1
        elif pattern and pattern != "unknown":
            n_pattern += 1

    return n_known, n_pattern


def repository_context(scraped_repository_path: Path) -> Dict[str, Any]:
    if not scraped_repository_path.exists():
        return {
            "repo_page_count": 0,
            "repo_chunk_count": 0,
            "has_repository_docs": False,
        }

    data = load_json(scraped_repository_path)

    if not data:
        return {
            "repo_page_count": 0,
            "repo_chunk_count": 0,
            "has_repository_docs": False,
        }

    page_count = data.get("metadata", {}).get("page_count", 0)
    chunks = data.get("chunks", [])
    chunk_count = len(chunks)

    return {
        "repo_page_count": page_count,
        "repo_chunk_count": chunk_count,
        "has_repository_docs": chunk_count >= 2,
    }


def validation_features(validation_dir: Path) -> Dict[str, Any]:
    accessible_dataset_urls = 0
    accessible_code_urls = 0
    total_accessible_urls = 0

    if not validation_dir.exists():
        return {
            "accessible_dataset_url_count": 0,
            "accessible_code_url_count": 0,
            "accessible_url_count": 0,
            "has_accessible_url": False,
        }

    for path in validation_dir.glob("*_validation.json"):
        data = load_json(path)
        if not data:
            continue

        n_accessible = 0

        for item in data.get("results", []):
            if item.get("accessible") is True:
                n_accessible += 1

        total_accessible_urls += n_accessible

        name = path.name.lower()

        if "dataset" in name:
            accessible_dataset_urls += n_accessible
        elif "code" in name or "repository" in name:
            accessible_code_urls += n_accessible

    return {
        "accessible_dataset_url_count": accessible_dataset_urls,
        "accessible_code_url_count": accessible_code_urls,
        "accessible_url_count": total_accessible_urls,
        "has_accessible_url": total_accessible_urls > 0,
    }


def code_generation_features(generated_manifest_path: Path) -> Dict[str, Any]:
    if not generated_manifest_path.exists():
        return {
            "generation_attempted": False,
            "generation_success": False,
            "generation_failure_category": "GEN_NOT_ATTEMPTED",
            "selected_file_count": 0,
            "has_expected_columns_in_codegen": False,
            "generation_warning_count": 0,
            "has_access_restriction_warning": False,
        }

    data = load_json(generated_manifest_path)

    if not data:
        return {
            "generation_attempted": True,
            "generation_success": False,
            "generation_failure_category": "GEN_MANIFEST_PARSE_FAILED",
            "selected_file_count": 0,
            "has_expected_columns_in_codegen": False,
            "generation_warning_count": 0,
            "has_access_restriction_warning": False,
        }

    failure = data.get("generation_failure")
    selected = data.get("selected_primary_files", []) or []
    warnings = data.get("generation_warnings", []) or []

    has_expected_columns = False

    for f in selected:
        cols = f.get("expected_columns")
        if isinstance(cols, list) and len(cols) > 0:
            has_expected_columns = True
            break

    has_access_warning = any(
        (w.get("category") == "GEN_ACCESS_RESTRICTED")
        for w in warnings
        if isinstance(w, dict)
    )

    failure_category = None

    if isinstance(failure, dict):
        failure_category = failure.get("category")

    return {
        "generation_attempted": True,
        "generation_success": failure is None,
        "generation_failure_category": failure_category,
        "selected_file_count": len(selected),
        "has_expected_columns_in_codegen": has_expected_columns,
        "generation_warning_count": len(warnings),
        "has_access_restriction_warning": has_access_warning,
    }


def extract_features_for_article(
    *,
    article_id: str,
    dataset_structure_path: Path,
    scraped_repository_path: Path,
    validation_dir: Path,
    generated_manifest_path: Path,
) -> Dict[str, Any] | None:
    ds = load_json(dataset_structure_path)

    if not ds:
        return None

    result = ds.get("result", {})

    if not isinstance(result, dict):
        return None

    org_type = (
        result.get("organization", {})
        .get("type", "unknown")
        if isinstance(result.get("organization"), dict)
        else "unknown"
    )

    try:
        structure_conf = float(result.get("structure_confidence") or 0.0)
    except Exception:
        structure_conf = 0.0

    files = result.get("files", [])

    if not isinstance(files, list):
        files = []

    n_files = len(files)
    n_tabular = 0
    n_supported_tabular = 0
    n_text = 0
    tabular_with_columns = 0
    has_any_columns = False
    total_columns = 0

    for f in files:
        if not isinstance(f, dict):
            continue

        schema_type = (f.get("schema_type") or "").lower()
        fmt = normalize_format(f.get("format"))

        if schema_type == "tabular":
            n_tabular += 1

            if fmt in SUPPORTED_TABULAR_FORMATS:
                n_supported_tabular += 1

            cols = f.get("structure", {}).get("columns", {})

            if isinstance(cols, dict) and len(cols) > 0:
                tabular_with_columns += 1
                has_any_columns = True
                total_columns += len(cols)

        if schema_type == "text":
            n_text += 1

    n_known_paths, n_pattern_paths = infer_path_accessibility(files)

    repo_feat = repository_context(scraped_repository_path)
    val_feat = validation_features(validation_dir)
    gen_feat = code_generation_features(generated_manifest_path)

    return {
        "article_id": article_id,
        "dataset_structure_path": str(dataset_structure_path),
        "generated_manifest_path": str(generated_manifest_path),

        "organization_type": org_type,
        "structure_confidence": structure_conf,

        "n_files": n_files,
        "n_tabular_files": n_tabular,
        "n_supported_tabular_files": n_supported_tabular,
        "n_text_files": n_text,

        "tabular_with_columns": tabular_with_columns,
        "has_any_columns": has_any_columns,
        "total_declared_columns": total_columns,

        "n_known_paths": n_known_paths,
        "n_pattern_paths": n_pattern_paths,

        **repo_feat,
        **val_feat,
        **gen_feat,
    }
