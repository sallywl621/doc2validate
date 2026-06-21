#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

RUN_NAME="${1:-}"
OLD_SD_ROOT="${2:-/mydata/SD_data}"

if [ -z "${RUN_NAME}" ]; then
  echo "Usage: bash scripts/build_pdf_manifest_from_existing_pdfs.sh <run_name> [old_sd_root]"
  echo "Example: bash scripts/build_pdf_manifest_from_existing_pdfs.sh scidata_4293 /mydata/SD_data"
  exit 1
fi

RUN_DIR="results/runs/${RUN_NAME}"
MANIFEST_DIR="${RUN_DIR}/manifests"
LOG_DIR="${RUN_DIR}/logs"

mkdir -p "${MANIFEST_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "data/raw_pdfs"

echo "Run name: ${RUN_NAME}"
echo "Old PDF root: ${OLD_SD_ROOT}"
echo "Output PDF dir: data/raw_pdfs"
echo "Manifest dir: ${MANIFEST_DIR}"

python - <<PY
from pathlib import Path
import pandas as pd
import shutil
from datetime import datetime

old_root = Path("${OLD_SD_ROOT}")
pdf_dir = Path("data/raw_pdfs")
manifest_dir = Path("${MANIFEST_DIR}")
log_path = Path("${LOG_DIR}") / "build_pdf_manifest_from_existing_pdfs.log"

pdf_dir.mkdir(parents=True, exist_ok=True)
manifest_dir.mkdir(parents=True, exist_ok=True)

rows = []
copied = 0
exists = 0
missing = 0

article_dirs = sorted([p for p in old_root.iterdir() if p.is_dir()])

with open(log_path, "w", encoding="utf-8") as log:
    log.write(f"started_at={datetime.now().isoformat()}\\n")
    log.write(f"old_root={old_root}\\n")
    log.write(f"article_dirs={len(article_dirs)}\\n")

    for d in article_dirs:
        article_id = d.name
        src_pdf = d / f"{article_id}.pdf"
        dst_pdf = pdf_dir / f"{article_id}.pdf"

        row = {
            "id": article_id,
            "article_id": article_id,
            "paper_id": article_id,
            "doi": article_id,
            "display_name": article_id,
            "title": "",
            "pdf_url": "",
            "pdf_path": str(dst_pdf),
            "download_status": "missing",
            "download_error": "",
            "source_pdf_path": str(src_pdf),
        }

        if not src_pdf.exists():
            missing += 1
            row["download_status"] = "missing"
            row["download_error"] = "source_pdf_not_found"
            rows.append(row)
            log.write(f"MISSING {article_id} {src_pdf}\\n")
            continue

        if dst_pdf.exists() and dst_pdf.stat().st_size > 0:
            exists += 1
            row["download_status"] = "exists"
            row["download_error"] = ""
            rows.append(row)
            continue

        try:
            shutil.copy2(src_pdf, dst_pdf)
            copied += 1
            row["download_status"] = "exists"
            row["download_error"] = ""
        except Exception as e:
            row["download_status"] = "failed"
            row["download_error"] = str(e)
            log.write(f"FAILED {article_id} {e}\\n")

        rows.append(row)

    df = pd.DataFrame(rows)
    out = manifest_dir / "pdf_manifest.csv"
    df.to_csv(out, index=False)

    # optional articles manifest for provenance
    articles_out = manifest_dir / "articles_manifest.csv"
    df[["id", "article_id", "paper_id", "doi", "display_name", "title"]].to_csv(
        articles_out,
        index=False,
    )

    log.write(f"finished_at={datetime.now().isoformat()}\\n")
    log.write(f"rows={len(df)}\\n")
    log.write(f"copied={copied}\\n")
    log.write(f"exists={exists}\\n")
    log.write(f"missing={missing}\\n")
    log.write(str(df["download_status"].value_counts()) + "\\n")

print("Wrote:", manifest_dir / "pdf_manifest.csv")
print("Rows:", len(rows))
print("Copied:", copied)
print("Already existed:", exists)
print("Missing:", missing)
print(pd.DataFrame(rows)["download_status"].value_counts())
PY

echo "Done."
echo "PDF manifest: ${MANIFEST_DIR}/pdf_manifest.csv"
echo "Log: ${LOG_DIR}/build_pdf_manifest_from_existing_pdfs.log"
