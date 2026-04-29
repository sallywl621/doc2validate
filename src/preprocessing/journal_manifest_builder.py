from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logging import setup_logging

OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def sanitize_id(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("._-") or "unknown"


def extract_slug(url: str) -> str:
    if not url:
        return ""
    name = Path(url.split("?")[0]).name
    if name.endswith(".pdf"):
        name = name[:-4]
    return sanitize_id(name)


def extract_pdf_url(work: Dict[str, Any]) -> str:
    return (
        (work.get("primary_location") or {}).get("pdf_url")
        or (work.get("best_oa_location") or {}).get("pdf_url")
        or ""
    )


def extract_landing_page(work: Dict[str, Any]) -> str:
    return (
        (work.get("primary_location") or {}).get("landing_page_url")
        or (work.get("best_oa_location") or {}).get("landing_page_url")
        or ""
    )


def extract_journal(work: Dict[str, Any]) -> str:
    return ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")


def infer_paper_id(work: Dict[str, Any]) -> str:
    return extract_slug(extract_pdf_url(work)) or extract_slug(extract_landing_page(work))


def is_likely_data_descriptor_openalex(work: Dict[str, Any]) -> bool:
    title = (work.get("display_name") or "").lower()
    keywords = ["dataset", "data descriptor", "database", "data set", "atlas", "catalog", "corpus"]
    return any(k in title for k in keywords)


def check_data_descriptor_in_page(url: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Original notebook rule:
    - only first <script>
    - only script.string
    - no lower()
    - no fallback
    """
    try:
        logging.info("[NATURE] fetching %s", url)
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        script_tag = soup.find("script")

        if script_tag:
            script_tag_contents = script_tag.string
            if script_tag_contents and "data descriptor" in script_tag_contents:
                return True, "original_match"

        return False, "original_no_match"

    except Exception as exc:
        logging.warning("[NATURE] error %s -> %s", url, exc)
        return False, "error"


def is_data_descriptor_nature(work: Dict[str, Any]) -> tuple[bool, str]:
    url = work.get("doi") or extract_landing_page(work)
    return check_data_descriptor_in_page(url)


def should_keep_work(work: Dict[str, Any], filter_mode: str) -> tuple[bool, str]:
    if filter_mode == "none":
        return True, "none"
    if filter_mode == "openalex":
        return is_likely_data_descriptor_openalex(work), "openalex"
    if filter_mode == "nature":
        return is_data_descriptor_nature(work)
    raise ValueError(f"Unsupported filter_mode: {filter_mode}")


def fetch_page(issn: str, cursor: str, per_page: int) -> dict:
    params = {
        "filter": f"primary_location.source.issn:{issn}",
        "per-page": per_page,
        "cursor": cursor,
    }
    logging.info("OpenAlex params: %s", params)

    response = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
    logging.info("OpenAlex response status: %s", response.status_code)
    response.raise_for_status()
    return response.json()


def build_manifest(
    issn: str,
    output_manifest: Path,
    max_articles: int,
    max_fetched: int,
    filter_mode: str,
    per_page: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    cursor = "*"
    records = []
    fetched = 0
    skipped = 0
    page = 0

    while len(records) < max_articles and fetched < max_fetched:
        page += 1
        logging.info("[PAGE] %d fetched=%d kept=%d skipped=%d", page, fetched, len(records), skipped)

        data = fetch_page(issn=issn, cursor=cursor, per_page=per_page)
        works = data.get("results", [])

        if not works:
            break

        for work in works:
            if fetched >= max_fetched:
                break

            fetched += 1
            paper_id = infer_paper_id(work)
            title = work.get("display_name", "")

            logging.info("[CHECK] %d id=%s title=%s", fetched, paper_id, title)

            keep, reason = should_keep_work(work, filter_mode)

            if not keep:
                skipped += 1
                logging.info("[SKIP] %s reason=%s", paper_id, reason)
                continue

            logging.info("[KEEP] %s reason=%s", paper_id, reason)

            records.append(
                {
                    "paper_id": paper_id,
                    "openalex_id": work.get("id", ""),
                    "doi": work.get("doi", ""),
                    "title": title,
                    "publication_year": work.get("publication_year", ""),
                    "journal": extract_journal(work),
                    "pdf_url": extract_pdf_url(work),
                    "landing_page": extract_landing_page(work),
                    "filter_mode": filter_mode,
                    "filter_reason": reason,
                }
            )

            if len(records) >= max_articles:
                break

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break

        time.sleep(sleep_seconds)

    df = pd.DataFrame(records)
    df.to_csv(output_manifest, index=False)

    logging.info("[DONE] saved %d records to %s", len(df), output_manifest)
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issn", required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--max-articles", type=int, default=20)
    parser.add_argument("--max-fetched", type=int, default=300)
    parser.add_argument("--filter-mode", choices=["none", "openalex", "nature"], default="openalex")
    parser.add_argument("--per-page", type=int, default=200)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--log-path", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_path)

    build_manifest(
        issn=args.issn,
        output_manifest=args.output_manifest,
        max_articles=args.max_articles,
        max_fetched=args.max_fetched,
        filter_mode=args.filter_mode,
        per_page=args.per_page,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == "__main__":
    main()
