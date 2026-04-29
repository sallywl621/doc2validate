from __future__ import annotations

from typing import Any, Dict, List

from src.context.context_builder import ContextBuilder
from src.extraction.base_extractor import BaseExtractor
from src.utils.config import LLM_CONFIG
from src.utils.llm_client import get_llm_client


class CodeRepositoryExtractor(BaseExtractor):
    def __init__(self):
        super().__init__("code_repository")
        self.context_builder = ContextBuilder(max_tokens=LLM_CONFIG.get("context_window", 32000))
        self.llm = get_llm_client()

    def get_context_strategy(self) -> str:
        return "section_focused_context"

    def get_section_priority(self) -> List[str]:
        return ["Code Availability", "Software Availability", "Data Availability", "Methods", "Analysis", "Supplementary Information"]

    def get_keywords(self) -> List[str]:
        return ["code availability", "software availability", "source code", "analysis code", "scripts", "github.com", "gitlab.com", "bitbucket.org", "repository", "implementation", "custom code"]

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "primary_code_repository": {
                "code_repository_urls": "list",
                "result_origin": "stated | inferred | null",
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
                "You are a scientific data curator. Identify code repositories that support generation, processing, "
                "analysis, or reuse of the PRIMARY dataset. Do not include generic software dependencies. "
                "Do not guess or fabricate URLs. Return JSON strictly following the schema."
            )
            user_prompt = f"""
Paper context:
----------------
{ctx.content}

Required schema:
{self.get_output_schema()}

Schema notes:
- code_repository_urls: list of repository URLs; empty list if none
- evidence.summary: explain why the repository supports the dataset
- evidence.key_quotes: quotes with section names
- references: formal identifiers if explicitly provided
"""
            raw = self.llm.generate(system_prompt, user_prompt)
            parsed = self.llm.parse_json_response(raw)
            parsed["context_summary"] = ctx.trace.__dict__
            return self.prepare_result(parsed, article_id)
        except Exception as exc:  # noqa: BLE001
            return self.handle_error(exc, article_id)
