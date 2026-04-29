from __future__ import annotations

import argparse
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


OPENALEX_WORKS_URL = "https://api.openalex.org/works"


# =========================
# Logging
# =========================
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


# =========================
# Utils
# =========================
def sanitize_id(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("._-") or "unknown"


def extract_slug(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if name.endswith(".pdf"):
        name = name[:-4]
    return sanitize_id(name)


def extract_pdf_url(work):
    return (
        (work.get("primary_location") or {}).get("pdf_url")
        or (work.get("best_oa_location") or {}).get("pdf_url")
        or ""
    )


def extract_landing_page(work):
    return (
        (work.get("primary_location") or {}).get("landing_page_url")
        or ""
    )


def extract_journal(work):
    return ((work.get("primary_location") or {}).get("source") or {}).get("display_name", "")


def infer_paper_id(work):
    pdf_url = extract_pdf_url(work)
    landing = extract_landing_page(work)

    return extract_slug(pdf_url) or extract_slug(landing)


# =========================
# OpenAlex Filter
# =========================
def is_likely_data_descriptor_openalex(work):
    title = (work.get("display_name") or "").lower()

    keywords = [
        "dataset", "data descriptor", "database",
        "data set", "atlas", "catalog", "corpus"
    ]

    return any(k in title for k in keywords)


# =========================
# ORIGINAL NOTEBOOK FILTER (DO NOT CHANGE)
# =========================
def check_data_descriptor_in_page(url: str, timeout: int = 10):
    """
    EXACT same logic as your notebook:
    - only first <script>
    - only script.string
    - no lower()
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

    except Exception as e:
        logging.warning("[NATURE] error %s -> %s", url, e)
        return False, "error"


def is_data_descriptor_nature(work):
    doi = work.get("doi") or ""
    landing = extract_landing_page(work)

    # 优先 DOI（和你 notebook 一样）
    url = doi or landing

    return check_data_descriptor_in_page(url)


# =========================
# Filter Dispatcher
# =========================
def should_keep_work(work, filter_mode):
    if filter_mode == "none":
        return True, "none"

    if filter_mode == "openalex":
        return is_likely_data_descriptor_openalex(work), "openalex"

    if filter_mode == "nature":
        keep, reason = is_data_descriptor_nature(work)
        return keep, reason

    raise ValueError(filter_mode)


# =========================
# Fetch OpenAlex
# =========================
def fetch_page(issn, cursor="*", per_page=200):
    params = {
        "filter": f"primary_location.source.issn:{issn}",
        "per-page": per_page,
        "cursor": cursor,
    }

    r = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# =========================
# Main Builder
# =========================
def build_manifest(
    issn: str,
    output: Path,
    max_articles: int,
    max_fetched: int,
    filter_mode: str,
):
    output.parent.mkdir(parents=True, exist_ok=True)

    cursor = "*"
    records = []

    fetched = 0
    skipped = 0
    page = 0

    while len(records) < max_articles and fetched < max_fetched:
        page += 1

        logging.info(
            "[PAGE] %d fetched=%d kept=%d skipped=%d",
            page, fetched, len(records), skipped
        )

        data = fetch_page(issn, cursor)
        works = data["results"]

        for w in works:
            if fetched >= max_fetched:
                break

            fetched += 1

            paper_id = infer_paper_id(w)

            logging.info(
                "[CHECK] %d id=%s title=%s",
                fetched,
                paper_id,
                w.get("display_name"),
            )

            keep, reason = should_keep_work(w, filter_mode)

            if not keep:
                skipped += 1
                logging.info("[SKIP] %s reason=%s", paper_id, reason)
                continue

            logging.info("[KEEP] %s reason=%s", paper_id, reason)

            records.append({
                "paper_id": paper_id,
                "doi": w.get("doi"),
                "title": w.get("display_name"),
                "journal": extract_journal(w),
                "pdf_url": extract_pdf_url(w),
                "landing_page": extract_landing_page(w),
            })

            if len(records) >= max_articles:
                break

        cursor = data["meta"]["next_cursor"]

    df = pd.DataFrame(records)
    df.to_csv(output, index=False)

    logging.info("[DONE] saved %d records", len(df))


# =========================
# CLI
# =========================
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--issn", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--max-articles", type=int, default=20)
    parser.add_argument("--max-fetched", type=int, default=300)
    parser.add_argument(
        "--filter-mode",
        choices=["none", "openalex", "nature"],
        default="openalex",
    )

    args = parser.parse_args()

    setup_logging()

    build_manifest(
        issn=args.issn,
        output=Path(args.output_manifest),
        max_articles=args.max_articles,
        max_fetched=args.max_fetched,
        filter_mode=args.filter_mode,
    )


if __name__ == "__main__":
    main()
