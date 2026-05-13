from __future__ import annotations

from typing import Any, Dict, List

from src.context.context_builder import ContextBuilder
from src.extraction.base_extractor import BaseExtractor
from src.utils.config import LLM_CONFIG
from src.utils.llm_client import get_llm_client


class DatasetExtractor(BaseExtractor):
    def __init__(self):
        super().__init__("dataset")
        self.context_builder = ContextBuilder(
            max_tokens=LLM_CONFIG.get("context_window", 32000)
        )
        self.llm = get_llm_client()

    def get_context_strategy(self) -> str:
        return "section_focused_context"

    def get_section_priority(self) -> List[str]:
        return [
            "Title",
            "Abstract",
            "Data Records",
            "Data Availability",
            "Methods",
        ]

    def get_keywords(self) -> List[str]:
        return [
            "dataset",
            "data set",
            "available at",
            "download",
            "DOI",
            "repository",
            "accession",
        ]

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "primary_dataset": {
                "name": "string | null",
                "name_origin": "stated | inferred | null",
                "description": "string",
                "access_urls": ["string"],
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
                "Your task is to identify the PRIMARY dataset introduced or curated by this paper.\n\n"
                "Selection rules:\n"
                "- If multiple datasets are mentioned, choose the one CREATED or CURATED by the authors.\n"
                "- Do not include secondary or reused datasets unless they are clearly the dominant dataset.\n"
                "- Do not invent names, URLs, identifiers, or access mechanisms.\n"
                "- Empty lists and null values are acceptable when information is not supported.\n\n"
                "Dataset naming:\n"
                "- If the dataset name is explicitly stated, use it and set name_origin to 'stated'.\n"
                "- If no official name is stated, infer a short descriptive name and set name_origin to 'inferred'.\n"
                "- Do not present inferred names as official names.\n\n"
                "Evidence rules:\n"
                "- evidence.key_quotes must be a JSON array of objects.\n"
                "- Each quote object must have exactly two fields: section and quote.\n"
                "- Do NOT append section names after a quote like: \"quote\" (Section).\n"
                "- Instead use: {\"section\": \"Section\", \"quote\": \"quote\"}.\n"
                "- Do NOT write text outside JSON strings.\n\n"
                "Confidence score rules:\n"
                "- 0.90–1.00: Primary dataset is clearly identified and has explicit access URL or DOI.\n"
                "- 0.60–0.80: Dataset is clearly described but access details are partial or indirect.\n"
                "- 0.30–0.50: Dataset is inferred with limited explicit evidence.\n"
                "- <0.30: Dataset identification is weak or ambiguous.\n"
                "- If access_urls is empty, confidence_score must be <= 0.80.\n"
                "- If both access_urls and references are empty, confidence_score must be <= 0.50.\n\n"
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
- access_urls must be a JSON array of strings.
- references must be a JSON array of strings.
- evidence.key_quotes must be a JSON array of objects:
  [
    {{"section": "Data Availability", "quote": "quoted text"}}
  ]
- Empty lists or null values are acceptable when unsupported.
"""

            raw = self.llm.generate(system_prompt, user_prompt)
            parsed = self.llm.parse_json_response(raw)
            parsed["context_summary"] = ctx.trace.__dict__

            return self.prepare_result(parsed, article_id)

        except Exception as exc:  # noqa: BLE001
            return self.handle_error(exc, article_id)
