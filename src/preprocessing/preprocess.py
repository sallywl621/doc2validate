from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.parse_pdf import parse_pdf_to_json, check_grobid_alive
from src.utils.logging import setup_logging


def infer_paper_id(row: pd.Series, pdf_path: Path) -> str:
    paper_id = row.get("paper_id", "")
    if pd.notna(paper_id) and str(paper_id).strip():
        return str(paper_id).strip()
    return pdf_path.stem


def append_status(record: Dict[str, Any], status_csv: Path) -> None:
    status_csv.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([record])
    df.to_csv(status_csv, mode="a", header=not status_csv.exists(), index=False)


def load_processed_ids(status_csv: Path) -> set[str]:
    if not status_csv.exists():
        return set()

    try:
        df = pd.read_csv(status_csv)
        if "paper_id" not in df.columns or "error" not in df.columns:
            return set()

        successful = df[df["error"] == False]  # noqa: E712
        return set(successful["paper_id"].dropna().astype(str))

    except Exception as exc:
        logging.warning("Could not read existing status CSV: %s", exc)
        return set()


def save_structured_json(pdf_data: Dict[str, Any], paper_id: str, output_dir: Path) -> Path:
    paper_dir = output_dir / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    output_path = paper_dir / "structured_data.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(pdf_data, file, indent=2, ensure_ascii=False)

    return output_path


def preprocess_one_pdf(
    row: pd.Series,
    structured_output_dir: Path,
    grobid_url: str,
    include_crossref_references: bool,
) -> Dict[str, Any]:
    start_time = time.time()
    start_datetime = datetime.now().isoformat()

    pdf_path = Path(str(row.get("local_pdf_path", "")))
    paper_id = infer_paper_id(row, pdf_path)

    if not pdf_path.exists():
        return {
            **row.to_dict(),
            "paper_id": paper_id,
            "error": True,
            "error_reason": f"PDF file not found: {pdf_path}",
            "processing_result": "failed",
            "structured_json_path": "",
            "start_time": start_datetime,
            "end_time": datetime.now().isoformat(),
            "processing_duration_seconds": round(time.time() - start_time, 2),
        }

    try:
        logging.info("[PROCESS] paper_id=%s pdf=%s", paper_id, pdf_path)

        pdf_data = parse_pdf_to_json(
            file_path=pdf_path,
            grobid_url=grobid_url,
            include_crossref_references=include_crossref_references,
        )

        if pdf_data is None:
            raise RuntimeError("parse_pdf_to_json returned None")

        pdf_data.setdefault("processing_info", {})
        pdf_data["processing_info"].update(
            {
                "paper_id": paper_id,
                "source_pdf_path": str(pdf_path),
                "processed_at": datetime.now().isoformat(),
                "include_crossref_references": include_crossref_references,
            }
        )

        output_path = save_structured_json(
            pdf_data=pdf_data,
            paper_id=paper_id,
            output_dir=structured_output_dir,
        )

        return {
            **row.to_dict(),
            "paper_id": paper_id,
            "error": False,
            "error_reason": "",
            "processing_result": "success",
            "structured_json_path": str(output_path),
            "chunk_count": len(pdf_data.get("chunks", [])),
            "section_count": pdf_data.get("metadata", {}).get("section_count", ""),
            "figure_count": pdf_data.get("metadata", {}).get("figure_count", ""),
            "start_time": start_datetime,
            "end_time": datetime.now().isoformat(),
            "processing_duration_seconds": round(time.time() - start_time, 2),
        }

    except Exception as exc:
        logging.exception("[FAIL] paper_id=%s", paper_id)
        return {
            **row.to_dict(),
            "paper_id": paper_id,
            "error": True,
            "error_reason": str(exc),
            "processing_result": "failed",
            "structured_json_path": "",
            "start_time": start_datetime,
            "end_time": datetime.now().isoformat(),
            "processing_duration_seconds": round(time.time() - start_time, 2),
        }


def preprocess_manifest(
    manifest_path: Path,
    structured_output_dir: Path,
    status_csv: Path,
    grobid_url: str,
    include_crossref_references: bool,
    resume: bool,
    sleep_seconds: float,
) -> pd.DataFrame:
    structured_output_dir.mkdir(parents=True, exist_ok=True)
    status_csv.parent.mkdir(parents=True, exist_ok=True)

    if not check_grobid_alive(grobid_url):
        logging.warning("GROBID service does not appear to be alive: %s", grobid_url)

    df = pd.read_csv(manifest_path)
    logging.info("Loaded PDF manifest: %d rows from %s", len(df), manifest_path)

    required_columns = {"paper_id", "local_pdf_path", "download_status"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Input manifest must be generated by pdf_downloader.py. Missing columns: {sorted(missing)}")

    before = len(df)
    df = df[df["download_status"].isin(["success", "exists"])].copy()
    logging.info("Filtered PDF manifest: %d -> %d rows with successful downloads", before, len(df))

    processed_ids = load_processed_ids(status_csv) if resume else set()

    for _, row in df.iterrows():
        pdf_path = Path(str(row.get("local_pdf_path", "")))
        paper_id = infer_paper_id(row, pdf_path)

        if resume and paper_id in processed_ids:
            logging.info("[SKIP PROCESSED] paper_id=%s", paper_id)
            continue

        record = preprocess_one_pdf(
            row=row,
            structured_output_dir=structured_output_dir,
            grobid_url=grobid_url,
            include_crossref_references=include_crossref_references,
        )

        append_status(record, status_csv)

        logging.info(
            "[RESULT] paper_id=%s result=%s error=%s",
            record.get("paper_id"),
            record.get("processing_result"),
            record.get("error_reason", ""),
        )

        time.sleep(sleep_seconds)

    result_df = pd.read_csv(status_csv) if status_csv.exists() else pd.DataFrame()

    if "error" in result_df.columns:
        logging.info("Preprocess status counts:\n%s", result_df["error"].value_counts(dropna=False))

    return result_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--structured-output-dir", type=Path, default=Path("data/structured_docs"))
    parser.add_argument("--status-csv", type=Path, default=Path("data/interim/preprocess_status.csv"))
    parser.add_argument("--grobid-url", type=str, default="http://localhost:8070")
    parser.add_argument("--no-crossref", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.1)
    parser.add_argument("--log-path", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_path)

    preprocess_manifest(
        manifest_path=args.manifest,
        structured_output_dir=args.structured_output_dir,
        status_csv=args.status_csv,
        grobid_url=args.grobid_url,
        include_crossref_references=not args.no_crossref,
        resume=not args.no_resume,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
