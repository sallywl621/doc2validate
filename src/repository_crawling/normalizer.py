from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_urls(urls: list[str]) -> list[str]:
    """
    Normalize repository URLs.

    Rules:
    - Remove duplicates
    - Remove fragments
    - Normalize missing scheme to https
    - Remove trailing slash from path
    """
    seen = set()
    result = []

    for url in urls:
        try:
            parsed = urlparse(url)

            clean = urlunparse(
                (
                    parsed.scheme or "https",
                    parsed.netloc,
                    parsed.path.rstrip("/"),
                    "",
                    "",
                    "",
                )
            )

        except Exception:
            continue

        if clean not in seen:
            seen.add(clean)
            result.append(clean)

    return result
