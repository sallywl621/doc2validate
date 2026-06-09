from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".json",
    ".jsonl",
    ".parquet",
    ".txt",
    ".ann",
    ".tar",
}

BLACKLIST_NAMES = {
    "ARTIFACT_DOWNLOAD_MANIFEST.json",
    "generated_manifest.json",
    "run_output.json",
}


def looks_like_pointer_file(path: Path) -> bool:
    try:
        if path.stat().st_size > 4096:
            return False

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).strip()

        markers = [
            ".git/annex/objects/",
            "../.git/annex",
            "version https://git-lfs.github.com/spec/v1",
            "oid sha256:",
        ]

        return any(m in text for m in markers)

    except Exception:
        return False


def read_columns(path: Path) -> list[str]:
    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            return [str(c) for c in pd.read_csv(path, nrows=0).columns]

        if suffix == ".tsv":
            return [str(c) for c in pd.read_csv(path, sep="\t", nrows=0).columns]

        if suffix in {".xlsx", ".xls"}:
            return [str(c) for c in pd.read_excel(path, nrows=0).columns]

        if suffix == ".parquet":
            return [str(c) for c in pd.read_parquet(path).columns]

        if suffix in {".json", ".jsonl"}:
            df = pd.read_json(path, lines=(suffix == ".jsonl"))
            return [str(c) for c in df.columns]

    except Exception:
        return []

    return []


def build_inventory(
    article_id: str,
    artifact_root: Path,
) -> dict[str, Any]:
    candidates = []

    if not artifact_root.exists():
        return {
            "article_id": article_id,
            "artifact_root": str(artifact_root),
            "candidate_count": 0,
            "candidate_files": [],
        }

    for path in artifact_root.rglob("*"):
        if not path.is_file():
            continue

        if path.name in BLACKLIST_NAMES:
            continue

        if path.is_symlink():
            continue

        suffix = path.suffix.lower()

        if suffix not in SUPPORTED_SUFFIXES:
            continue

        if looks_like_pointer_file(path):
            continue

        rel = path.relative_to(artifact_root)

        candidates.append(
            {
                "relative_path": str(rel),
                "absolute_path": str(path),
                "filename": path.name,
                "stem": path.stem,
                "suffix": suffix,
                "format": suffix.lstrip("."),
                "size_bytes": path.stat().st_size,
                "columns": read_columns(path)[:80],
                "path_parts": list(rel.parts),
            }
        )

    return {
        "article_id": article_id,
        "artifact_root": str(artifact_root),
        "candidate_count": len(candidates),
        "candidate_files": candidates,
    }


def save_inventory(
    article_id: str,
    artifact_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    payload = build_inventory(
        article_id=article_id,
        artifact_root=artifact_root,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return payload
