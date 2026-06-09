from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


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

        return any(marker in text for marker in markers)

    except Exception:
        return False


def read_csv_preview(
    path: Path,
    n_rows: int = 5,
) -> dict[str, Any]:
    encodings = [
        "utf-8",
        "utf-8-sig",
        "latin1",
        "cp1252",
    ]

    last_error = None

    for encoding in encodings:
        try:
            df = pd.read_csv(
                path,
                nrows=n_rows,
                encoding=encoding,
                low_memory=False,
            )

            return {
                "ok": True,
                "encoding": encoding,
                "columns": [str(c) for c in df.columns],
                "first_rows": df.astype(str).fillna("").to_dict(
                    orient="records"
                ),
                "error": None,
            }

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    return {
        "ok": False,
        "encoding": None,
        "columns": [],
        "first_rows": [],
        "error": last_error,
    }


def build_csv_previews(
    article_id: str,
    artifact_root: Path,
    n_rows: int = 5,
) -> dict[str, Any]:
    files = []

    if not artifact_root.exists():
        return {
            "article_id": article_id,
            "artifact_root": str(artifact_root),
            "csv_file_count": 0,
            "files": [],
        }

    for path in sorted(artifact_root.rglob("*.csv")):
        if not path.is_file():
            continue

        if path.name in BLACKLIST_NAMES:
            continue

        if path.is_symlink():
            continue

        if looks_like_pointer_file(path):
            continue

        rel = path.relative_to(artifact_root)

        preview = read_csv_preview(
            path,
            n_rows=n_rows,
        )

        files.append(
            {
                "relative_path": str(rel),
                "absolute_path": str(path),
                "filename": path.name,
                "stem": path.stem,
                "size_bytes": path.stat().st_size,
                "path_parts": list(rel.parts),
                "preview": preview,
            }
        )

    return {
        "article_id": article_id,
        "artifact_root": str(artifact_root),
        "csv_file_count": len(files),
        "files": files,
    }


def save_csv_previews(
    article_id: str,
    artifact_root: Path,
    output_path: Path,
    n_rows: int = 5,
) -> dict[str, Any]:
    payload = build_csv_previews(
        article_id=article_id,
        artifact_root=artifact_root,
        n_rows=n_rows,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return payload
