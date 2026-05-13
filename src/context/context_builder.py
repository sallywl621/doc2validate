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
    """
    Build LLM context from paper sections and optional scraped repository content.

    Design goals:
    1. Paper content is treated as the primary source.
    2. Repository content is treated as supporting evidence.
    3. Repository content has its own token budget so it cannot dominate the prompt.
    4. If the selected sections are small enough, the builder may upgrade to fulltext context.
    """

    def __init__(
        self,
        max_tokens: int = 32000,
        max_repository_tokens: int = 8000,
    ):
        """
        Args:
            max_tokens:
                Maximum total context budget passed to the LLM.

            max_repository_tokens:
                Maximum number of tokens allowed from scraped repository content.
                This prevents large repository pages from overwhelming paper content.
        """
        self.max_tokens = max_tokens
        self.max_repository_tokens = max_repository_tokens

    def build_context(
        self,
        article_id: str,
        *,
        strategy: str,
        section_priority: List[str],
        keywords: List[str] | None = None,
    ) -> ContextResult:
        structure = get_article_structure(article_id)
        sections = self._load_sections(structure)

        if not sections:
            raise RuntimeError(f"No context sections loaded for article_id={article_id}")

        section_content, sections_used = self._assemble_by_priority(
            sections=sections,
            priority=section_priority,
        )

        if not section_content.strip() and keywords:
            section_content, sections_used = self._assemble_by_keywords(
                sections=sections,
                keywords=keywords,
            )

        if not section_content.strip():
            section_content = self._assemble_fulltext(sections)
            sections_used = list(sections.keys())

        section_tokens = estimate_tokens_from_string(section_content)

        effective_strategy = strategy
        upgraded = False
        upgrade_reason = None
        content = section_content

        # Upgrade to fulltext only when the entire paper + repository context fits.
        # Repository content is already capped during loading.
        if strategy != "fulltext_context" and section_tokens < self.max_tokens:
            fulltext_content = self._assemble_fulltext(sections)
            fulltext_tokens = estimate_tokens_from_string(fulltext_content)

            if fulltext_tokens <= self.max_tokens:
                content = fulltext_content
                effective_strategy = "fulltext_context"
                upgraded = True
                upgrade_reason = "fulltext_within_token_limit"

        original_tokens = estimate_tokens_from_string(content)
        truncated = False

        if original_tokens > self.max_tokens:
            content = self._truncate(content)
            truncated = True

        final_tokens = estimate_tokens_from_string(content)

        effective_sections = (
            list(sections.keys())
            if effective_strategy == "fulltext_context"
            else sections_used
        )

        trace = ContextTrace(
            requested_strategy=strategy,
            effective_strategy=effective_strategy,
            upgraded=upgraded,
            upgrade_reason=upgrade_reason,
            sections_used=effective_sections,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            truncated=truncated,
            token_breakdown=self._estimate_token_breakdown(content),
        )

        return ContextResult(
            article_id=article_id,
            content=content,
            token_count=final_tokens,
            timestamp=datetime.now().isoformat(),
            trace=trace,
        )

    def _load_sections(self, structure: Dict) -> Dict[str, List[str]]:
        """
        Load sections from:
        - structured_data.json
        - scraped_repository.json

        Paper sections are loaded first.
        Repository sections are loaded second and are capped by max_repository_tokens.
        """
        sections: Dict[str, List[str]] = {}

        json_dir: Path = structure["json_data_dir"]

        structured_path = json_dir / "structured_data.json"
        if structured_path.exists():
            self._load_chunked_json(
                path=structured_path,
                sections=sections,
                source_tag="PAPER",
                max_source_tokens=None,
            )

        scraped_repo_path = json_dir / "scraped_repository.json"
        if scraped_repo_path.exists():
            self._load_chunked_json(
                path=scraped_repo_path,
                sections=sections,
                source_tag="REPOSITORY",
                max_source_tokens=self.max_repository_tokens,
            )

        return sections

    def _load_chunked_json(
        self,
        path: Path,
        sections: Dict[str, List[str]],
        *,
        source_tag: str,
        max_source_tokens: int | None = None,
    ) -> None:
        """
        Load chunk-style JSON into the internal section dictionary.

        If max_source_tokens is provided, loading stops once the source token budget
        is reached. This is mainly used for repository content.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        used_tokens = 0

        for chunk in data.get("chunks", []):
            title = chunk.get("sectitle") or "Unknown"
            text = (chunk.get("text") or "").strip()

            if not text:
                continue

            text_tokens = estimate_tokens_from_string(text)

            if max_source_tokens is not None:
                if used_tokens >= max_source_tokens:
                    break

                remaining_tokens = max_source_tokens - used_tokens

                if text_tokens > remaining_tokens:
                    text = self._truncate_to_token_budget(text, remaining_tokens)
                    text_tokens = estimate_tokens_from_string(text)

            section_key = f"[{source_tag}] {title}"
            sections.setdefault(section_key, []).append(text)

            used_tokens += text_tokens

    def _assemble_by_priority(
        self,
        sections: Dict[str, List[str]],
        priority: List[str],
    ) -> Tuple[str, List[str]]:
        """
        Assemble context using user-provided section priority.

        Recommended priority order:
        - Paper evidence first
        - Repository evidence later

        Example:
            [
                "Data Availability",
                "Code Availability",
                "Methods",
                "Scraped Repository"
            ]
        """
        parts: List[str] = []
        used: List[str] = []

        for item in priority:
            for sec_title, texts in sections.items():
                if item.lower() in sec_title.lower():
                    if sec_title not in used:
                        parts.append(f"## {sec_title}")
                        parts.extend(texts)
                        used.append(sec_title)

        return "\n\n".join(parts), used

    def _assemble_by_keywords(
        self,
        sections: Dict[str, List[str]],
        keywords: List[str],
    ) -> Tuple[str, List[str]]:
        parts: List[str] = []
        used: List[str] = []

        lowered_keywords = [kw.lower() for kw in keywords]

        for sec_title, texts in sections.items():
            combined_text = "\n".join(texts)
            search_text = f"{sec_title}\n{combined_text}".lower()

            if any(keyword in search_text for keyword in lowered_keywords):
                parts.append(f"## {sec_title}")
                parts.extend(texts)
                used.append(sec_title)

        return "\n\n".join(parts), used

    def _assemble_fulltext(self, sections: Dict[str, List[str]]) -> str:
        parts: List[str] = []

        for sec_title, texts in sections.items():
            parts.append(f"## {sec_title}")
            parts.extend(texts)

        return "\n\n".join(parts)

    def _truncate(self, text: str) -> str:
        approx_chars = self.max_tokens * 3
        return text[:approx_chars] + "\n\n[CONTENT TRUNCATED]"

    def _truncate_to_token_budget(self, text: str, max_tokens: int) -> str:
        """
        Approximate token-aware truncation.

        This uses the same rough token heuristic as the rest of the project.
        """
        if max_tokens <= 0:
            return ""

        approx_chars = max_tokens * 3
        return text[:approx_chars] + "\n\n[REPOSITORY CONTENT TRUNCATED]"

    def _estimate_token_breakdown(self, content: str) -> Dict[str, int]:
        breakdown = {
            "paper_tokens": 0,
            "repository_tokens": 0,
        }

        current_source = None
        buffer: List[str] = []

        def flush() -> None:
            nonlocal buffer, current_source

            if not buffer or not current_source:
                buffer = []
                return

            text = "\n".join(buffer)
            tokens = estimate_tokens_from_string(text)

            if current_source == "PAPER":
                breakdown["paper_tokens"] += tokens
            elif current_source == "REPOSITORY":
                breakdown["repository_tokens"] += tokens

            buffer = []

        for line in content.splitlines():
            if line.startswith("## [PAPER]"):
                flush()
                current_source = "PAPER"
                continue

            if line.startswith("## [REPOSITORY]"):
                flush()
                current_source = "REPOSITORY"
                continue

            buffer.append(line)

        flush()

        return breakdown
