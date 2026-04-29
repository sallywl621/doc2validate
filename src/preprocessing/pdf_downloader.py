from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import requests


def setup_logging(log_path: Optional[Path] = None) -> None:
    handlers = [logging.StreamHandler()]

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def sanitize_filename(value: str) -> str:
    value = str(value).strip()
    value = value.replace("/", "_")
    value = value.replace("\\", "_")
    value = value.replace(":", "_")
    value = value.replace("?", "_")
    value = value.replace("&", "_")
    value = value.replace("=", "_")
    return value or "unknown_paper"


def get_pdf_filename(row: pd.Series) -> str:
    paper_id = row.get("paper_id", "")

    if pd.notna(paper_id) and str(paper_id).strip():
        return f"{sanitize_filename(str(paper_id))}.pdf"

    pdf_url = row.get("pdf_url", "")
    if pd.notna(pdf_url) and str(pdf_url).strip():
        name = Path(str(pdf_url).split("?")[0]).name
        if name:
            return sanitize_filename(name)

    doi = row.get("doi", "")
    if pd.notna(doi) and str(doi).strip():
        return f"{sanitize_filename(str(doi).split('/')[-1])}.pdf"

    return "unknown_paper.pdf"


def download_pdf(
    pdf_url: str,
    output_path: Path,
    timeout: int = 90,
    overwrite: bool = False,
) -> Tuple[str, str, int]:
    """
    Download one PDF.

    Returns:
        download_status, download_error, file_size_bytes
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.stat().st_size > 0 and not overwrite:
        return "exists", "", output_path.stat().st_size

    if not pdf_url:
        return "no_pdf_url", "Missing pdf_url", 0

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 Doc2Validate PDF downloader"
        }

        response = requests.get(
            pdf_url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        )

        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        with output_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)

        file_size = output_path.stat().st_size if output_path.exists() else 0

        if file_size == 0:
            return "failed", "Downloaded file is empty", 0

        if "pdf" not in content_type and not output_path.name.lower().endswith(".pdf"):
            return "success_non_pdf_content_type", f"content-type={content_type}", file_size

        return "success", "", file_size

    except requests.exceptions.Timeout:
        return "failed", "timeout", 0

    except requests.exceptions.RequestException as exc:
        return "failed", f"request_error: {exc}", 0

    except Exception as exc:
        return "failed", f"unexpected_error: {exc}", 0


def load_existing_successes(output_manifest: Path) -> set[str]:
    """
    Load already successful or existing downloads from an existing output manifest.
    Used for resume mode.
    """
    if not output_manifest.exists():
        return set()

    try:
        df = pd.read_csv(output_manifest)

        if "paper_id" not in df.columns or "download_status" not in df.columns:
            return set()

        successful = df[df["download_status"].isin(["success", "exists"])]
        return set(successful["paper_id"].dropna().astype(str))

    except Exception as exc:
        logging.warning("Could not read existing output manifest: %s", exc)
        return set()


def append_record(record: Dict, output_manifest: Path) -> None:
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    record_df = pd.DataFrame([record])
    write_header = not output_manifest.exists()

    record_df.to_csv(
        output_manifest,
        mode="a",
        header=write_header,
        index=False,
    )


def download_from_manifest(
    input_manifest: Path,
    output_manifest: Path,
    pdf_dir: Path,
    overwrite: bool = False,
    resume: bool = True,
    only_failed: bool = False,
    sleep_seconds: float = 0.2,
    timeout: int = 90,
) -> pd.DataFrame:
    """
    Download PDFs listed in an article manifest.

    Input manifest columns expected:
        paper_id
        pdf_url

    Output manifest columns added:
        pdf_filename
        local_pdf_path
        download_status
        download_error
        file_size_bytes
    """
    pdf_dir.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_manifest)
    logging.info("Loaded input manifest: %d rows from %s", len(df), input_manifest)

    processed_success_ids = load_existing_successes(output_manifest) if resume else set()

    records = []

    for index, row in df.iterrows():
        paper_id = str(row.get("paper_id", "") or "")

        if resume and paper_id in processed_success_ids and not overwrite:
            logging.info("[SKIP EXISTS] %d/%d paper_id=%s", index + 1, len(df), paper_id)
            continue

        if only_failed:
            existing_status = str(row.get("download_status", "") or "")
            if existing_status not in {"failed", "no_pdf_url"}:
                continue

        pdf_url = row.get("pdf_url", "")
        pdf_url = "" if pd.isna(pdf_url) else str(pdf_url)

        pdf_filename = get_pdf_filename(row)
        local_pdf_path = pdf_dir / pdf_filename

        logging.info(
            "[DOWNLOAD] %d/%d paper_id=%s url=%s",
            index + 1,
            len(df),
            paper_id,
            pdf_url,
        )

        status, error, file_size = download_pdf(
            pdf_url=pdf_url,
            output_path=local_pdf_path,
            timeout=timeout,
            overwrite=overwrite,
        )

        record = row.to_dict()
        record.update(
            {
                "pdf_filename": pdf_filename,
                "local_pdf_path": str(local_pdf_path),
                "download_status": status,
                "download_error": error,
                "file_size_bytes": file_size,
            }
        )

        append_record(record, output_manifest)
        records.append(record)

        logging.info(
            "[RESULT] paper_id=%s status=%s size=%s error=%s",
            paper_id,
            status,
            file_size,
            error,
        )

        time.sleep(sleep_seconds)

    if output_manifest.exists():
        out_df = pd.read_csv(output_manifest)
    else:
        out_df = pd.DataFrame(records)

    if "download_status" in out_df.columns:
        logging.info("Download status counts:\n%s", out_df["download_status"].value_counts(dropna=False))

    logging.info("Wrote PDF manifest to %s", output_manifest)
    return out_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download PDFs from an article manifest and write a PDF manifest."
    )

    parser.add_argument(
        "--input-manifest",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-manifest",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=Path("data/raw_pdfs"),
    )

    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--only-failed", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--log-path", type=Path, default=None)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_path)

    download_from_manifest(
        input_manifest=args.input_manifest,
        output_manifest=args.output_manifest,
        pdf_dir=args.pdf_dir,
        overwrite=args.overwrite,
        resume=not args.no_resume,
        only_failed=args.only_failed,
        sleep_seconds=args.sleep_seconds,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
