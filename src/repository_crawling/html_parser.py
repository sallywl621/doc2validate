from __future__ import annotations

import re
from bs4 import BeautifulSoup


BLOCKED_TEXT_KEYWORDS = [
    "privacy policy",
    "cookie policy",
    "terms of use",
    "terms and conditions",
    "accessibility",
    "copyright",
    "all rights reserved",
    "subscribe",
    "newsletter",
    "sign in",
    "log in",
    "login",
    "register",
    "share this",
    "follow us",
    "contact us",
    "citation",
    "how to cite",
]


def normalize_text(text: str) -> str:
    """
    Normalize whitespace and remove control characters.
    """
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    return text.strip()


def is_low_value_text(text: str) -> bool:
    """
    Filter boilerplate or navigation-like text.

    The crawler is intended to preserve dataset/repository evidence, not full
    website chrome such as privacy notices, login prompts, or citation widgets.
    """
    if not text:
        return True

    lowered = text.lower()

    if len(text) < 30:
        return True

    if any(keyword in lowered for keyword in BLOCKED_TEXT_KEYWORDS):
        return True

    # Remove very link-like fragments.
    if lowered.count("http") >= 3:
        return True

    # Remove fragments that are mostly symbols or punctuation.
    alpha_chars = sum(ch.isalpha() for ch in text)
    if alpha_chars / max(len(text), 1) < 0.4:
        return True

    return False


def parse_html_to_text(html: str) -> str:
    """
    Convert HTML into clean text for repository-aware extraction.

    Kept elements:
    - headings
    - paragraphs
    - list items
    - table cells

    Removed elements:
    - scripts
    - styles
    - navigation
    - headers/footers
    - forms
    - buttons
    - boilerplate text
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "form",
            "button",
            "noscript",
            "svg",
            "aside",
        ]
    ):
        tag.decompose()

    texts = []

    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        text = normalize_text(elem.get_text(" ", strip=True))

        if is_low_value_text(text):
            continue

        texts.append(text)

    # Deduplicate while preserving order.
    deduped = []
    seen = set()

    for text in texts:
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)

    return "\n".join(deduped)
