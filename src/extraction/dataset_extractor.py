from __future__ import annotations

from typing import Any, Dict, List

from src.context.context_builder import ContextBuilder
from src.extraction.base_extractor import BaseExtractor
from src.utils.config import LLM_CONFIG
from src.utils.llm_client import get_llm_client


class DatasetExtractor(BaseExtractor):
    def __init__(self):
        super().__init__("dataset")
        self.context_builder = ContextBuilder(max_tokens=LLM_CONFIG.get("context_window", 32000))
        self.llm = get_llm_client()

    def get_context_strategy(self) -> str:
        return "section_focused_context"

    def get_section_priority(self) -> List[str]:
        return ["Title", "Abstract", "Data Records", "Data Availability", "Methods"]

    def get_keywords(self) -> List[str]:
        return ["dataset", "data set", "available at", "download", "DOI", "repository", "accession"]

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "primary_dataset": {
                "name": "string | null",
                "name_origin": "stated | inferred | null",
                "description": "string",
                "access_urls": "list",
                "references": "list",
                "evidence": {"summary": "string", "key_quotes": "list"},
            },
            "confidence_score": "float",
        }

    def extract(self, article_id: str, article_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        try:
            ctx = self.context_builder.build_context(
                article_id=article_id,
                strategy=self.get_context_strategy(),
                section_priority=self.get_section_priority(),
                keywords=self.get_keywords(),
            )
            system_prompt = (
                "You are a scientific data curator. Identify the PRIMARY dataset introduced or curated by this paper. "
                "If multiple datasets are mentioned, choose the one created or curated by the authors. "
                "Do not invent unsupported fields. Return JSON strictly following the schema."
            )
            user_prompt = f"""
Paper context:
----------------
{ctx.content}

Required schema:
{self.get_output_schema()}

Schema notes:
- evidence.summary: concise explanation of why this is the primary dataset
- evidence.key_quotes: direct or near-direct quotes from the paper with section names
- references: dataset-specific identifiers explicitly stated in the paper
- Empty lists or null values are acceptable when unsupported
"""
            raw = self.llm.generate(system_prompt, user_prompt)
            parsed = self.llm.parse_json_response(raw)
            parsed["context_summary"] = ctx.trace.__dict__
            return self.prepare_result(parsed, article_id)
        except Exception as exc:  # noqa: BLE001
            return self.handle_error(exc, article_id)
