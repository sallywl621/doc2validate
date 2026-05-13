from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List
from urllib.parse import urlparse

import requests

MAX_RETRIES = 3
BASE_SLEEP = 2
DOMAIN_COOLDOWN = 1.0
USER_AGENT = "Doc2Validate/1.0"

DOMAIN_LAST_ACCESS = defaultdict(float)


def respect_domain_rate_limit(domain: str) -> None:
    now = time.time()
    elapsed = now - DOMAIN_LAST_ACCESS[domain]

    if elapsed < DOMAIN_COOLDOWN:
        time.sleep(DOMAIN_COOLDOWN - elapsed)

    DOMAIN_LAST_ACCESS[domain] = time.time()


def fetch_html_with_retry(url: str) -> str | None:
    domain = urlparse(url).netloc

    for attempt in range(MAX_RETRIES):
        try:
            respect_domain_rate_limit(domain)

            resp = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": USER_AGENT},
            )

            if resp.status_code != 200:
                raise requests.RequestException(f"HTTP {resp.status_code}")

            content_type = resp.headers.get("Content-Type", "")

            if "text/html" not in content_type:
                return None

            return resp.text

        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                print(f"[WARN] fetch failed: {url} ({exc})")
                return None

            time.sleep(BASE_SLEEP * (2**attempt))

    return None


def crawl_repository(
    root_urls: List[str],
    max_depth: int = 2,
    max_pages_per_domain: int = 20,
) -> List[Dict]:
    """
    Crawl repository landing pages.

    Current behavior:
    - Fetch only provided root URLs.
    - Respect per-domain page limits.
    - Keep max_depth argument for future recursive crawling.
    """
    unique_urls = list(dict.fromkeys(root_urls))
    domains = {urlparse(u).netloc for u in unique_urls}

    print(
        f"[INFO] Repository crawl started | "
        f"raw_urls={len(root_urls)}, "
        f"unique_urls={len(unique_urls)}, "
        f"domains={len(domains)}, "
        f"max_depth={max_depth}"
    )

    pages = []
    visited = set()
    domain_counter = defaultdict(int)

    for url in unique_urls:
        domain = urlparse(url).netloc

        if domain_counter[domain] >= max_pages_per_domain:
            continue

        if url in visited:
            continue

        html = fetch_html_with_retry(url)
        visited.add(url)

        if not html:
            continue

        pages.append(
            {
                "url": url,
                "html": html,
            }
        )

        domain_counter[domain] += 1

    print(f"[INFO] Repository crawl finished | pages_fetched={len(pages)}")

    return pages
