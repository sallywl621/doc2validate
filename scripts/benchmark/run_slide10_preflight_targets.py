#!/usr/bin/env python3
from pathlib import Path
import csv
import json
import os
from collections import Counter, defaultdict

BENCHMARK_ROOT = Path("/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1")
MANIFEST_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "manifests"
OUT_DIR = BENCHMARK_ROOT / "grounding_v2_hardfilter_0618" / "validation_slide10"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILE_MANIFEST = MANIFEST_DIR / "presentation_grounding_v2_file_manifest.csv"
COLUMN_MANIFEST = MANIFEST_DIR / "presentation_grounding_v2_column_manifest.csv"
ARTICLE_MANIFEST = MANIFEST_DIR / "presentation_grounding_v2_article_manifest.csv"

TARGET_CSV = OUT_DIR / "slide10_validation_targets.csv"
SUMMARY_JSON = OUT_DIR / "slide10_preflight_summary.json"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_int(x, default=0):
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default


def is_false(x):
    return str(x).strip().lower() in {"false", "0", "no", "n", ""}


def nonempty(x):
    return x is not None and str(x).strip() != ""


def artifact_root(article_id):
    return BENCHMARK_ROOT / article_id / "artifact"


def split_possible_paths(text):
    if not text:
        return []
    text = str(text).replace("\\", "/").strip()
    pieces = []
    for sep in [";", "\n", "|", ","]:
        if sep in text:
            for p in text.split(sep):
                p = p.strip().strip("'\"[]{}")
                if p:
                    pieces.append(p)
            return pieces
    return [text.strip().strip("'\"[]{}")]


def resolve_artifact_path(article_id, path_text):
    """
    Try to resolve manifest relative path to an actual file under article artifact/.
    """
    root = artifact_root(article_id)
    if not root.exists():
        return None

    candidates = split_possible_paths(path_text)

    # Direct tries
    for raw in candidates:
        raw = raw.replace("\\", "/").strip()
        if not raw:
            continue

        direct_candidates = [
            root / raw,
            root / "github" / raw,
        ]

        for c in direct_candidates:
            if c.exists():
                return c

    # Suffix / basename search
    files = [p for p in root.rglob("*") if p.is_file()]
    for raw in candidates:
        raw = raw.replace("\\", "/").strip()
        if not raw:
            continue

        basename = Path(raw).name

        suffix_hits = []
        basename_hits = []

        for p in files:
            rel = str(p.relative_to(root)).replace("\\", "/")
            full = str(p).replace("\\", "/")

            if rel.endswith(raw) or raw.endswith(rel) or full.endswith(raw):
                suffix_hits.append(p)

            if basename and p.name == basename:
                basename_hits.append(p)

        if suffix_hits:
            return suffix_hits[0]
        if basename_hits:
            return basename_hits[0]

    return None


files = read_csv(FILE_MANIFEST)
cols = read_csv(COLUMN_MANIFEST)
articles = read_csv(ARTICLE_MANIFEST)

resolved_files = [r for r in files if r.get("grounding_status") == "resolved"]

matched_cols = [
    r for r in cols
    if nonempty(r.get("matched_column"))
]

official_total_matched_columns = sum(as_int(r.get("total_matched_columns")) for r in articles)

# For automation-ready validation, use columns that do not need human review.
auto_matched_cols = [
    r for r in cols
    if nonempty(r.get("matched_column")) and is_false(r.get("human_review_needed"))
]

cols_by_file = defaultdict(list)
for r in auto_matched_cols:
    key = (r.get("article_id"), r.get("logical_file_id"))
    cols_by_file[key].append(r)

target_rows = []

SUPPORTED_SUFFIXES = {".csv", ".tsv", ".xlsx"}

for f in resolved_files:
    article_id = f.get("article_id")
    logical_file_id = f.get("logical_file_id")
    suffix = (f.get("observed_suffix") or "").lower().strip()
    header_status = f.get("header_load_status")

    key = (article_id, logical_file_id)
    file_cols = cols_by_file.get(key, [])

    if not file_cols:
        continue

    if suffix not in SUPPORTED_SUFFIXES:
        continue

    # Prefer matched_or_candidate_path from file manifest.
    path_text = f.get("matched_or_candidate_path") or ""
    resolved_path = resolve_artifact_path(article_id, path_text)

    # If file-level path failed, try column manifest matched_physical_file.
    if resolved_path is None and file_cols:
        resolved_path = resolve_artifact_path(article_id, file_cols[0].get("matched_physical_file"))

    target_rows.append({
        "article_id": article_id,
        "logical_file_id": logical_file_id,
        "logical_name": f.get("logical_name"),
        "observed_suffix": suffix,
        "header_load_status": header_status,
        "num_documented_columns": f.get("num_documented_columns"),
        "num_matched_columns_file_manifest": f.get("num_matched_columns"),
        "num_auto_matched_column_rows": len(file_cols),
        "unique_matched_columns": len(set(c.get("matched_column") for c in file_cols if nonempty(c.get("matched_column")))),
        "matched_columns": "|".join(sorted(set(c.get("matched_column") for c in file_cols if nonempty(c.get("matched_column"))))),
        "manifest_path": path_text,
        "resolved_physical_path": str(resolved_path) if resolved_path else "",
        "path_resolved": bool(resolved_path),
    })


# Write target CSV
fieldnames = [
    "article_id",
    "logical_file_id",
    "logical_name",
    "observed_suffix",
    "header_load_status",
    "num_documented_columns",
    "num_matched_columns_file_manifest",
    "num_auto_matched_column_rows",
    "unique_matched_columns",
    "matched_columns",
    "manifest_path",
    "resolved_physical_path",
    "path_resolved",
]

with TARGET_CSV.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(target_rows)


summary = {
    "manifest_dir": str(MANIFEST_DIR),
    "resolved_files": len(resolved_files),
    "resolved_files_with_documented_columns": sum(as_int(r.get("num_documented_columns")) > 0 for r in resolved_files),
    "documented_columns_under_resolved_files": sum(as_int(r.get("num_documented_columns")) for r in resolved_files),
    "official_total_matched_columns": official_total_matched_columns,
    "column_manifest_nonempty_matched_column_rows": len(matched_cols),
    "auto_matched_column_rows_human_review_false": len(auto_matched_cols),
    "validation_candidate_files_csv_tsv_xlsx": len(target_rows),
    "validation_candidate_files_with_resolved_path": sum(r["path_resolved"] for r in target_rows),
    "candidate_suffix_distribution": dict(Counter(r["observed_suffix"] for r in target_rows)),
    "candidate_unique_column_total": sum(r["unique_matched_columns"] for r in target_rows),
    "output_target_csv": str(TARGET_CSV),
}

with SUMMARY_JSON.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(json.dumps(summary, indent=2, ensure_ascii=False))

print("\nTop candidate files by matched columns:")
for r in sorted(target_rows, key=lambda x: (x["unique_matched_columns"], x["num_auto_matched_column_rows"]), reverse=True)[:15]:
    print(
        f"{r['article_id']} | {r['logical_file_id']} | "
        f"{r['logical_name']} | {r['observed_suffix']} | "
        f"unique_cols={r['unique_matched_columns']} | "
        f"path_resolved={r['path_resolved']}"
    )

print("\nWrote:")
print(TARGET_CSV)
print(SUMMARY_JSON)
