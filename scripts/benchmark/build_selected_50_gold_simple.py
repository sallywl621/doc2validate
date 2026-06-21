#!/usr/bin/env python3
"""
Build a simplified selected-50 gold benchmark directory.

User-specified rules:

1. Read the 50 article_ids from selected_run_50.xlsx, preferably sheet "selected_50".
2. Copy known article-level JSON/PDF files into:
   /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/<article_id>/
3. For existing GitHub downloaded artifacts:
   copy only every .../extracted directory under
   /mydata/doc2validate/data/downloaded_artifacts/<article_id>/
   into:
   <article_id>/artifact/github/
4. For listed manually downloaded replacement archives in /tmp/0612_download:
   extract each zip into:
   <article_id>/artifact/<new_source>/
   where new_source is figshare or osf.
5. Write logs and manifests.

Default input:
  selected xlsx: /mnt/data/selected_run_50.xlsx
  manual downloads: /tmp/0612_download
  data root: /mydata/doc2validate/data
  output root: /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1

Run:
  python build_selected_50_gold_simple.py \
    --selected-xlsx /path/to/selected_run_50.xlsx \
    --manual-download-dir /tmp/0612_download \
    --data-root /mydata/doc2validate/data \
    --output-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
    --overwrite
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import shutil
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


DEFAULT_SELECTED_XLSX = Path("/mnt/data/selected_run_50.xlsx")
DEFAULT_DATA_ROOT = Path("/mydata/doc2validate/data")
DEFAULT_RUN_ROOT = Path("/mydata/doc2validate/results/runs/scidata_4293")
DEFAULT_MANUAL_DOWNLOAD_DIR = Path("/tmp/0612_download")
DEFAULT_OUTPUT_ROOT = Path("/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1")

# Manual external replacements specified by user.
MANUAL_REPLACEMENTS = [
    {"article_id": "s41597-019-0035-4", "new_source": "figshare", "zip_name": "7097879.zip"},
    {"article_id": "s41597-020-00688-8", "new_source": "figshare", "zip_name": "12673217.zip"},
    {"article_id": "s41597-022-01696-6", "new_source": "figshare", "zip_name": "17304221.zip"},
    {"article_id": "s41597-023-02070-w", "new_source": "figshare", "zip_name": "21035857.zip"},
    {"article_id": "s41597-023-02094-2", "new_source": "figshare", "zip_name": "21938102.zip"},
    {"article_id": "s41597-023-02717-8", "new_source": "figshare", "zip_name": "23623935.zip"},
    {"article_id": "s41597-024-03120-7", "new_source": "figshare", "zip_name": "24259573.zip"},
    {"article_id": "sdata2018310", "new_source": "figshare", "zip_name": "7185194.zip"},
    {"article_id": "s41597-021-00844-8", "new_source": "figshare", "zip_name": "12656165.zip"},
    {"article_id": "s41597-023-02310-z", "new_source": "osf", "zip_name": "osfstorage-archive.zip"},
]

ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".gz")
JSON_COPY_NAMES = {
    "dataset_structure.json",
    "dataset_url_validation.json",
    "code_repository_validation.json",
    "scraped_repository.json",
    "dataset.json",
    "code_repository.json",
    "structured_data.json",
    "ARTIFACT_DOWNLOAD_MANIFEST.json",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_load_json(path: Path) -> Any:
    if not path.exists():
        return None
    for enc in ("utf-8", "utf-8-sig"):
        try:
            with path.open("r", encoding=enc) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path, overwrite: bool = True) -> bool:
    if not src.exists() or not src.is_file():
        return False
    ensure_dir(dst.parent)
    if dst.exists() and not overwrite:
        return False
    shutil.copy2(src, dst)
    return True


def copy_tree(src: Path, dst: Path, overwrite: bool = True) -> bool:
    if not src.exists() or not src.is_dir():
        return False
    if dst.exists():
        if overwrite:
            shutil.rmtree(dst)
        else:
            return False
    ensure_dir(dst.parent)
    shutil.copytree(src, dst)
    return True


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


def dir_size_mb(path: Path) -> float:
    total = 0
    if path.exists():
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total / 1024 / 1024


def safe_name(s: str) -> str:
    s = str(s)
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    return s[:180] or "unnamed"


def extract_archive(src: Path, dst: Path, overwrite: bool = True) -> Tuple[str, str]:
    """
    Extract src into dst. For non-archive files, copy src into dst.
    """
    if overwrite and dst.exists():
        shutil.rmtree(dst)
    ensure_dir(dst)

    name = src.name.lower()

    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(dst)
            return "extracted", "zip"

        if name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz"):
            mode = "r:gz" if (name.endswith(".tar.gz") or name.endswith(".tgz")) else "r:"
            with tarfile.open(src, mode) as tf:
                tf.extractall(dst)
            return "extracted", "tar"

        if name.endswith(".gz"):
            out_path = dst / src.name[:-3]
            with gzip.open(src, "rb") as f_in, out_path.open("wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            return "extracted", "gz"

        copy_file(src, dst / src.name)
        return "copied", "not_archive"

    except Exception as exc:
        return "failed", str(exc)


def pick_selected_sheet(xlsx_path: Path, sheet_name: Optional[str] = None) -> str:
    xl = pd.ExcelFile(xlsx_path)

    preferred = []
    if sheet_name:
        preferred.append(sheet_name)
    preferred.extend(["selected_50", "selected", "Sheet1"])

    for s in preferred:
        if s in xl.sheet_names:
            return s

    for s in xl.sheet_names:
        cols = list(pd.read_excel(xlsx_path, sheet_name=s, nrows=0).columns)
        if any(str(c).strip().lower() == "article_id" for c in cols):
            return s

    raise ValueError(f"No sheet with article_id found. Sheets={xl.sheet_names}")


def read_selected_article_ids(xlsx_path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    sheet = pick_selected_sheet(xlsx_path, sheet_name)
    df = pd.read_excel(xlsx_path, sheet_name=sheet)

    # Normalize article_id column.
    article_col = None
    for c in df.columns:
        if str(c).strip().lower() == "article_id":
            article_col = c
            break

    if article_col is None:
        raise ValueError(f"Sheet {sheet} has no article_id column.")

    df = df.copy()
    df["article_id"] = df[article_col].astype(str).str.strip()
    df = df[df["article_id"].str.len() > 0]
    df = df.drop_duplicates(subset=["article_id"], keep="first").reset_index(drop=True)
    df["selected_sheet"] = sheet
    return df


def find_pdf(article_id: str, data_root: Path, run_root: Path) -> Optional[Path]:
    """
    Search likely locations for article PDF.
    This is intentionally broad but only returns the first matched PDF.
    """
    roots = [
        data_root / "pdfs",
        data_root / "articles",
        data_root / "raw_pdfs",
        data_root / "structured_docs" / article_id,
        run_root,
        data_root,
    ]

    patterns = [
        f"{article_id}.pdf",
        f"*{article_id}*.pdf",
    ]

    for root in roots:
        if not root.exists():
            continue
        for pat in patterns:
            matches = sorted(root.rglob(pat))
            if matches:
                return matches[0]

    return None


def copy_article_process_files(article_id: str, data_root: Path, run_root: Path, case_dir: Path) -> Dict[str, Any]:
    """
    Copy known JSON/PDF files for a case.

    Output:
      <article_id>/json/
      <article_id>/pdf/
    """
    json_dir = case_dir / "json"
    pdf_dir = case_dir / "pdf"
    ensure_dir(json_dir)
    ensure_dir(pdf_dir)

    copied_json = []
    copied_pdf = []

    structured_dir = data_root / "structured_docs" / article_id

    if structured_dir.exists():
        for p in structured_dir.rglob("*.json"):
            # Copy all json under validation, and known json elsewhere.
            if p.parent.name == "validation" or p.name in JSON_COPY_NAMES:
                rel = p.relative_to(structured_dir)
                dst = json_dir / rel
                if copy_file(p, dst):
                    copied_json.append(str(dst.relative_to(case_dir)))

    # Also copy artifact download manifest.
    artifact_manifest = data_root / "downloaded_artifacts" / article_id / "ARTIFACT_DOWNLOAD_MANIFEST.json"
    if artifact_manifest.exists():
        dst = json_dir / "ARTIFACT_DOWNLOAD_MANIFEST.json"
        if copy_file(artifact_manifest, dst):
            copied_json.append(str(dst.relative_to(case_dir)))

    # Copy run-level related JSON/CSV manifests if article-specific files exist.
    # Keep this conservative: do not copy huge global manifests into every case.

    pdf = find_pdf(article_id, data_root, run_root)
    if pdf:
        dst = pdf_dir / pdf.name
        if copy_file(pdf, dst):
            copied_pdf.append(str(dst.relative_to(case_dir)))

    return {
        "structured_docs_dir": str(structured_dir),
        "json_files_copied_count": len(copied_json),
        "json_files_copied": "; ".join(copied_json),
        "pdf_found": bool(pdf),
        "pdf_source_path": str(pdf) if pdf else "",
        "pdf_files_copied_count": len(copied_pdf),
        "pdf_files_copied": "; ".join(copied_pdf),
    }


def copy_existing_extracted_to_github(article_id: str, data_root: Path, case_dir: Path, overwrite: bool = True) -> Dict[str, Any]:
    """
    Copy only .../extracted directories under downloaded_artifacts/<article_id>
    to <article_id>/artifact/github/.

    The destination preserves a readable provider/repo parent name:
      artifact/github/<parent_path_safe>/
    """
    src_article_dir = data_root / "downloaded_artifacts" / article_id
    dst_github_root = case_dir / "artifact" / "github"
    ensure_dir(dst_github_root)

    extracted_dirs = []
    if src_article_dir.exists():
        for p in src_article_dir.rglob("extracted"):
            if p.is_dir():
                extracted_dirs.append(p)

    copied = []
    for p in sorted(extracted_dirs):
        rel_parent = p.parent.relative_to(src_article_dir)
        dst = dst_github_root / safe_name(str(rel_parent))
        if copy_tree(p, dst, overwrite=overwrite):
            copied.append(str(dst.relative_to(case_dir)))

    return {
        "downloaded_artifacts_dir": str(src_article_dir),
        "github_extracted_dirs_found": len(extracted_dirs),
        "github_extracted_dirs_copied": len(copied),
        "github_extracted_destinations": "; ".join(copied),
        "github_artifact_file_count": count_files(dst_github_root),
        "github_artifact_size_mb": dir_size_mb(dst_github_root),
    }


def find_manual_zip(manual_download_dir: Path, zip_name: str) -> Optional[Path]:
    direct = manual_download_dir / zip_name
    if direct.exists():
        return direct

    matches = sorted(manual_download_dir.rglob(zip_name))
    if matches:
        return matches[0]

    # Case-insensitive fallback.
    lower = zip_name.lower()
    for p in sorted(manual_download_dir.rglob("*")):
        if p.is_file() and p.name.lower() == lower:
            return p

    return None


def apply_manual_replacements(
    article_id: str,
    manual_download_dir: Path,
    case_dir: Path,
    overwrite: bool = True,
) -> List[Dict[str, Any]]:
    rows = []
    replacements = [r for r in MANUAL_REPLACEMENTS if r["article_id"] == article_id]

    for r in replacements:
        new_source = r["new_source"]
        zip_name = r["zip_name"]
        src_zip = find_manual_zip(manual_download_dir, zip_name)
        dst_source_dir = case_dir / "artifact" / new_source
        original_dir = case_dir / "artifact" / "original_external_archives" / new_source
        ensure_dir(dst_source_dir)
        ensure_dir(original_dir)

        row = {
            "article_id": article_id,
            "new_source": new_source,
            "zip_name": zip_name,
            "manual_zip_found": bool(src_zip),
            "manual_zip_path": str(src_zip) if src_zip else "",
            "manual_extract_dir": str(dst_source_dir),
            "manual_extract_status": "",
            "manual_extract_reason": "",
            "manual_file_count": 0,
            "manual_size_mb": 0.0,
        }

        if not src_zip:
            row["manual_extract_status"] = "missing_zip"
            row["manual_extract_reason"] = f"not_found_under_{manual_download_dir}"
            rows.append(row)
            continue

        copied_zip = original_dir / src_zip.name
        copy_file(src_zip, copied_zip)

        status, reason = extract_archive(copied_zip, dst_source_dir, overwrite=overwrite)

        row["manual_extract_status"] = status
        row["manual_extract_reason"] = reason
        row["manual_copied_zip_path"] = str(copied_zip)
        row["manual_file_count"] = count_files(dst_source_dir)
        row["manual_size_mb"] = dir_size_mb(dst_source_dir)
        rows.append(row)

    return rows


def write_case_readme(case_dir: Path, article_id: str, manual_rows: List[Dict[str, Any]]) -> None:
    lines = [
        f"# Gold benchmark case: {article_id}",
        "",
        "## Structure",
        "",
        "- `json/`: copied article-level JSON and validation files.",
        "- `pdf/`: article PDF if found.",
        "- `artifact/github/`: copied existing downloaded `extracted` directories.",
        "- `artifact/figshare/` or `artifact/osf/`: manually downloaded replacement artifact, if specified.",
        "- `artifact/original_external_archives/`: copied original manual zip files.",
        "",
    ]

    if manual_rows:
        lines.extend(["## Manual replacement artifacts", ""])
        for r in manual_rows:
            lines.append(f"- {r['new_source']}: {r['zip_name']} -> {r['manual_extract_status']} ({r['manual_extract_reason']})")
        lines.append("")

    (case_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def build_case(
    article_id: str,
    data_root: Path,
    run_root: Path,
    manual_download_dir: Path,
    output_root: Path,
    overwrite: bool = True,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    case_dir = output_root / article_id
    if overwrite and case_dir.exists():
        shutil.rmtree(case_dir)

    ensure_dir(case_dir)
    ensure_dir(case_dir / "artifact")
    ensure_dir(case_dir / "json")
    ensure_dir(case_dir / "pdf")

    row: Dict[str, Any] = {
        "article_id": article_id,
        "case_dir": str(case_dir),
        "started_at": now(),
    }

    row.update(copy_article_process_files(article_id, data_root, run_root, case_dir))
    row.update(copy_existing_extracted_to_github(article_id, data_root, case_dir, overwrite=overwrite))

    manual_rows = apply_manual_replacements(article_id, manual_download_dir, case_dir, overwrite=overwrite)

    row["has_manual_replacement"] = len(manual_rows) > 0
    row["manual_sources"] = "; ".join(sorted({r["new_source"] for r in manual_rows}))
    row["manual_zip_names"] = "; ".join([r["zip_name"] for r in manual_rows])
    row["manual_all_found"] = all(r["manual_zip_found"] for r in manual_rows) if manual_rows else True
    row["manual_total_file_count"] = sum(int(r["manual_file_count"]) for r in manual_rows)
    row["manual_total_size_mb"] = sum(float(r["manual_size_mb"]) for r in manual_rows)

    row["total_artifact_file_count"] = count_files(case_dir / "artifact")
    row["total_artifact_size_mb"] = dir_size_mb(case_dir / "artifact")
    row["finished_at"] = now()
    row["build_status"] = "success"

    write_case_readme(case_dir, article_id, manual_rows)

    # Case-level metadata
    with (case_dir / "case_build_manifest.json").open("w", encoding="utf-8") as f:
        json.dump({"case": row, "manual_replacements": manual_rows}, f, indent=2, ensure_ascii=False)

    return row, manual_rows


def write_root_readme(output_root: Path, selected_xlsx: Path, n_cases: int) -> None:
    text = f"""# SciData selected 50 gold benchmark v1

Generated at: {now()}

This directory was built from `{selected_xlsx}`.

Rules used:

1. For each selected article, copy known JSON/PDF files into `<article_id>/json/` and `<article_id>/pdf/`.
2. Copy only existing `downloaded_artifacts/<article_id>/**/extracted/` directories into `<article_id>/artifact/github/`.
3. Extract manually downloaded replacement zip files from `/tmp/0612_download` into `<article_id>/artifact/<new_source>/`.
4. Write `benchmark_manifest.csv`, `manual_replacement_log.csv`, and per-case `case_build_manifest.json`.

Total selected cases: {n_cases}
"""
    (output_root / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build simplified selected-50 gold benchmark.")
    parser.add_argument("--selected-xlsx", type=Path, default=DEFAULT_SELECTED_XLSX)
    parser.add_argument("--selected-sheet", type=str, default=None)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--manual-download-dir", type=Path, default=DEFAULT_MANUAL_DOWNLOAD_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing case directories.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.selected_xlsx.exists():
        raise FileNotFoundError(f"selected xlsx not found: {args.selected_xlsx}")

    ensure_dir(args.output_root)

    selected = read_selected_article_ids(args.selected_xlsx, args.selected_sheet)
    article_ids = selected["article_id"].astype(str).tolist()

    print("Selected cases:", len(article_ids))
    print("Selected sheet:", selected["selected_sheet"].iloc[0] if len(selected) else "")
    print("Output root:", args.output_root)
    print("Manual download dir:", args.manual_download_dir)
    print("Manual replacements expected:", len(MANUAL_REPLACEMENTS))

    if args.dry_run:
        print("Dry run. Article IDs:")
        for aid in article_ids:
            print(aid)
        return

    # Copy workbook to root.
    copy_file(args.selected_xlsx, args.output_root / "selected_run_50.xlsx")

    manifest_rows = []
    manual_log_rows = []
    build_errors = []

    for i, article_id in enumerate(article_ids, start=1):
        print(f"[{i}/{len(article_ids)}] {article_id}")
        try:
            row, manual_rows = build_case(
                article_id=article_id,
                data_root=args.data_root,
                run_root=args.run_root,
                manual_download_dir=args.manual_download_dir,
                output_root=args.output_root,
                overwrite=args.overwrite,
            )
            manifest_rows.append(row)
            manual_log_rows.extend(manual_rows)
        except Exception as exc:
            error_row = {
                "article_id": article_id,
                "case_dir": str(args.output_root / article_id),
                "build_status": "failed",
                "error": str(exc),
                "finished_at": now(),
            }
            print("  FAILED:", exc)
            manifest_rows.append(error_row)
            build_errors.append(error_row)

    manifest_df = pd.DataFrame(manifest_rows)
    manifest_df.to_csv(args.output_root / "benchmark_manifest.csv", index=False)

    with (args.output_root / "benchmark_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest_rows, f, indent=2, ensure_ascii=False)

    manual_df = pd.DataFrame(manual_log_rows)
    if len(manual_df):
        manual_df.to_csv(args.output_root / "manual_replacement_log.csv", index=False)
    else:
        # Still create empty file with expected columns.
        pd.DataFrame(columns=[
            "article_id", "new_source", "zip_name", "manual_zip_found",
            "manual_zip_path", "manual_extract_dir", "manual_extract_status",
            "manual_extract_reason", "manual_file_count", "manual_size_mb",
        ]).to_csv(args.output_root / "manual_replacement_log.csv", index=False)

    # Article id list.
    with (args.output_root / "selected_50_article_ids.txt").open("w", encoding="utf-8") as f:
        for aid in article_ids:
            f.write(aid + "\n")

    # Copy script into output root for reproducibility.
    try:
        shutil.copy2(Path(__file__), args.output_root / "build_selected_50_gold_simple.py")
    except Exception:
        pass

    write_root_readme(args.output_root, args.selected_xlsx, len(article_ids))

    print("\nDone.")
    print("benchmark_manifest:", args.output_root / "benchmark_manifest.csv")
    print("manual_replacement_log:", args.output_root / "manual_replacement_log.csv")
    print("selected IDs:", args.output_root / "selected_50_article_ids.txt")

    print("\nSummary:")
    if "build_status" in manifest_df.columns:
        print(manifest_df["build_status"].value_counts(dropna=False).to_string())
    if "has_manual_replacement" in manifest_df.columns:
        print("\nhas_manual_replacement:")
        print(manifest_df["has_manual_replacement"].value_counts(dropna=False).to_string())
    if "manual_all_found" in manifest_df.columns:
        print("\nmanual_all_found:")
        print(manifest_df["manual_all_found"].value_counts(dropna=False).to_string())
    if len(manual_df) and "manual_extract_status" in manual_df.columns:
        print("\nmanual_extract_status:")
        print(manual_df["manual_extract_status"].value_counts(dropna=False).to_string())

    if build_errors:
        print("\nBuild errors:")
        for e in build_errors:
            print(e)


if __name__ == "__main__":
    main()
