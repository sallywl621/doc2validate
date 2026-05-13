from __future__ import annotations

from typing import Any, Dict, List

from src.context.context_builder import ContextBuilder
from src.extraction.base_extractor import BaseExtractor
from src.utils.config import LLM_CONFIG
from src.utils.llm_client import get_llm_client


class CodeRepositoryExtractor(BaseExtractor):
    def __init__(self):
        super().__init__("code_repository")
        self.context_builder = ContextBuilder(
            max_tokens=LLM_CONFIG.get("context_window", 32000)
        )
        self.llm = get_llm_client()

    def get_context_strategy(self) -> str:
        return "section_focused_context"

    def get_section_priority(self) -> List[str]:
        return [
            "Code Availability",
            "Software Availability",
            "Data Availability",
            "Methods",
            "Analysis",
            "Supplementary Information",
        ]

    def get_keywords(self) -> List[str]:
        return [
            "code availability",
            "software availability",
            "source code",
            "analysis code",
            "scripts",
            "github.com",
            "gitlab.com",
            "bitbucket.org",
            "repository",
            "implementation",
            "custom code",
        ]

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "primary_code_repository": {
                "code_repository_urls": ["string"],
                "result_origin": "stated | inferred | null",
                "references": ["string"],
                "evidence": {
                    "summary": "string",
                    "key_quotes": [
                        {
                            "section": "string",
                            "quote": "string",
                        }
                    ],
                },
            },
            "confidence_score": "float",
        }

    def extract(
        self,
        article_id: str,
        article_result: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            ctx = self.context_builder.build_context(
                article_id=article_id,
                strategy=self.get_context_strategy(),
                section_priority=self.get_section_priority(),
                keywords=self.get_keywords(),
            )

            system_prompt = (
                "You are a scientific data curator.\n\n"
                "Your task is to identify code repositories that support the generation, "
                "processing, analysis, or reuse of the PRIMARY dataset described in this paper.\n\n"
                "Inclusion rules:\n"
                "- Include repositories containing data processing scripts, analysis pipelines, "
                "data generation code, reproducibility workflows, or dataset-specific implementation code.\n"
                "- Repositories must be explicitly stated in the paper or clearly implied as being created "
                "or used by the authors for this dataset.\n\n"
                "Exclusion rules:\n"
                "- Do NOT include generic software tools, libraries, packages, or unrelated GitHub links.\n"
                "- Do NOT include repositories mentioned only as dependencies or background tools.\n"
                "- Do NOT include data repositories unless they also clearly contain code.\n"
                "- Do NOT guess or fabricate repository URLs.\n\n"
                "Result origin:\n"
                "- stated: the repository URL is explicitly mentioned in the paper.\n"
                "- inferred: the repository is clearly implied but the exact URL is not directly quoted.\n"
                "- null: no supporting code repository is identified.\n\n"
                "Evidence rules:\n"
                "- evidence.key_quotes must be a JSON array of objects.\n"
                "- Each quote object must have exactly two fields: section and quote.\n"
                "- Do NOT append section names after a quote like: \"quote\" (Section).\n"
                "- Instead use: {\"section\": \"Section\", \"quote\": \"quote\"}.\n"
                "- Do NOT write text outside JSON strings.\n\n"
                "Confidence score rules:\n"
                "- 0.90–1.00: Explicit code repository URL is provided and clearly linked to dataset support.\n"
                "- 0.60–0.80: Code repository is clearly described but URL is indirect or partial.\n"
                "- 0.30–0.50: Code support is implied with weak or indirect evidence.\n"
                "- <0.30: Code availability is ambiguous or unsupported.\n"
                "- If code_repository_urls is empty, confidence_score must be <= 0.30.\n"
                "- Do NOT assign high confidence to the absence of a repository.\n\n"
                "Return ONLY valid JSON. Do not use Markdown. Do not include explanations outside JSON."
            )

            user_prompt = f"""
Paper context:
----------------
{ctx.content}

Required JSON schema:
{self.get_output_schema()}

Output requirements:
- Return one JSON object only.
- code_repository_urls must be a JSON array of strings.
- references must be a JSON array of strings.
- evidence.key_quotes must be a JSON array of objects:
  [
    {{"section": "Code Availability", "quote": "quoted text"}}
  ]
- If no code repository is identified:
  - code_repository_urls must be []
  - result_origin must be null
  - confidence_score must be <= 0.30
"""

            raw = self.llm.generate(system_prompt, user_prompt)
            parsed = self.llm.parse_json_response(raw)
            parsed["context_summary"] = ctx.trace.__dict__

            return self.prepare_result(parsed, article_id)

        except Exception as exc:  # noqa: BLE001
            return self.handle_error(exc, article_id)
