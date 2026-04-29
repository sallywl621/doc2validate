from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from src.utils.config import get_article_structure
from src.utils.tokens import estimate_tokens_from_string


@dataclass
class ContextTrace:
    requested_strategy: str
    effective_strategy: str
    upgraded: bool
    upgrade_reason: str | None
    sections_used: List[str]
    original_tokens: int
    final_tokens: int
    truncated: bool
    token_breakdown: Dict[str, int]


@dataclass
class ContextResult:
    article_id: str
    content: str
    token_count: int
    timestamp: str
    trace: ContextTrace


class ContextBuilder:
    """Build paper-only context from data/structured_docs/<article_id>/structured_data.json."""

    def __init__(self, max_tokens: int = 32000):
        self.max_tokens = max_tokens

    def build_context(
        self,
        article_id: str,
        *,
        strategy: str,
        section_priority: List[str],
        keywords: List[str] | None = None,
    ) -> ContextResult:
        structure = get_article_structure(article_id)
        sections = self._load_sections(structure["structured_data_path"])
        if not sections:
            raise RuntimeError(f"No sections loaded for {article_id}")

        section_content, sections_used = self._assemble_by_priority(sections, section_priority)
        if not section_content.strip() and keywords:
            section_content, sections_used = self._assemble_by_keywords(sections, keywords)
        if not section_content.strip():
            section_content, sections_used = self._assemble_by_priority(sections, list(sections.keys()))

        effective_strategy = strategy
        upgraded = False
        upgrade_reason = None
        content = section_content

        if strategy != "fulltext_context":
            fulltext = self._assemble_fulltext(sections)
            if estimate_tokens_from_string(fulltext) <= self.max_tokens:
                content = fulltext
                effective_strategy = "fulltext_context"
                upgraded = True
                upgrade_reason = "fulltext_within_token_limit"
                sections_used = list(sections.keys())

        original_tokens = estimate_tokens_from_string(content)
        truncated = False
        if original_tokens > self.max_tokens:
            content = self._truncate(content)
            truncated = True

        final_tokens = estimate_tokens_from_string(content)
        trace = ContextTrace(
            requested_strategy=strategy,
            effective_strategy=effective_strategy,
            upgraded=upgraded,
            upgrade_reason=upgrade_reason,
            sections_used=sections_used,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            truncated=truncated,
            token_breakdown={"paper_tokens": final_tokens, "repository_tokens": 0},
        )
        return ContextResult(article_id, content, final_tokens, datetime.now().isoformat(), trace)

    def _load_sections(self, structured_data_path: Path) -> Dict[str, List[str]]:
        with structured_data_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        sections: Dict[str, List[str]] = {}
        chunks = data.get("chunks", [])
        if isinstance(chunks, list):
            for chunk in chunks:
                title = chunk.get("sectitle") or chunk.get("section") or "Unknown"
                text = (chunk.get("text") or "").strip()
                if text:
                    sections.setdefault(f"[PAPER] {title}", []).append(text)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.strip():
                    sections.setdefault(f"[PAPER] {key}", []).append(value.strip())
        return sections

    def _assemble_by_priority(self, sections: Dict[str, List[str]], priority: List[str]) -> Tuple[str, List[str]]:
        parts: List[str] = []
        used: List[str] = []
        for p in priority:
            for title, texts in sections.items():
                if p.lower() in title.lower() and title not in used:
                    parts.append(f"## {title}")
                    parts.extend(texts)
                    used.append(title)
        return "\n\n".join(parts), used

    def _assemble_by_keywords(self, sections: Dict[str, List[str]], keywords: List[str]) -> Tuple[str, List[str]]:
        parts: List[str] = []
        used: List[str] = []
        lowered = [k.lower() for k in keywords]
        for title, texts in sections.items():
            joined = "\n\n".join(texts)
            haystack = f"{title}\n{joined}".lower()
            if any(k in haystack for k in lowered):
                parts.append(f"## {title}")
                parts.extend(texts)
                used.append(title)
        return "\n\n".join(parts), used

    def _assemble_fulltext(self, sections: Dict[str, List[str]]) -> str:
        parts: List[str] = []
        for title, texts in sections.items():
            parts.append(f"## {title}")
            parts.extend(texts)
        return "\n\n".join(parts)

    def _truncate(self, text: str) -> str:
        return text[: self.max_tokens * 3] + "\n\n[CONTENT TRUNCATED]"
