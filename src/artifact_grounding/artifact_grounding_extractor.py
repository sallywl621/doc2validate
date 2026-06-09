from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.artifact_grounding.physical_inventory_builder import save_inventory
from src.extraction.base_extractor import BaseExtractor
from src.utils.config import DATA_DIR, LLM_CONFIG
from src.utils.llm_client import get_llm_client


class ArtifactGroundingExtractor(BaseExtractor):
    """
    Artifact Grounding Extractor

    Responsibilities:
    - Take logical dataset files from dataset_structure.json
    - Take physical file inventory from downloaded artifacts
    - Ask LLM to map logical files to physical repository files
    - Return a grounding manifest for downstream code generation
    """

    def __init__(self):
        super().__init__("artifact_grounding")
        self.llm = get_llm_client()

    def get_context_strategy(self) -> str:
        return "artifact_grounding"

    def get_section_priority(self) -> List[str]:
        return []

    def get_keywords(self) -> List[str]:
        return []

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "resolutions": [
                {
                    "logical_name": "string",
                    "file_pattern": "string | unknown",
                    "expected_format": "string | unknown",
                    "grounding_status": "resolved | ambiguous | unresolved",
                    "resolved_relative_path": "string | null",
                    "confidence": "float between 0 and 1",
                    "reason": "string",
                }
            ],
            "grounding_confidence": "float between 0 and 1",
        }

    def extract(
        self,
        article_id: str,
        article_result: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            artifact_root = DATA_DIR / "downloaded_artifacts" / article_id

            article_dir = DATA_DIR / "structured_docs" / article_id
            dataset_structure_path = article_dir / "dataset_structure.json"

            if not dataset_structure_path.exists():
                raise FileNotFoundError(
                    f"dataset_structure.json not found: {dataset_structure_path}"
                )

            dataset_structure = json.loads(
                dataset_structure_path.read_text(
                    encoding="utf-8",
                )
            )

            inventory_output_path = (
                DATA_DIR
                / "structured_docs"
                / article_id
                / "artifact_grounding_inventory.json"
            )

            inventory = save_inventory(
                article_id=article_id,
                artifact_root=artifact_root,
                output_path=inventory_output_path,
            )

            logical_files = (
                dataset_structure
                .get("result", {})
                .get("files", [])
            )

            compact_logical_files = []
            for f in logical_files:
                structure = f.get("structure", {}) or {}
                columns = structure.get("columns", {}) or {}

                compact_logical_files.append(
                    {
                        "logical_name": f.get("logical_name"),
                        "file_pattern": f.get("file_pattern"),
                        "format": f.get("format"),
                        "schema_type": f.get("schema_type"),
                        "role": f.get("role"),
                        "path": f.get("path"),
                        "expected_columns": list(columns.keys())[:20],
                    }
                )

            compact_candidates = []
            for c in inventory.get("candidate_files", []):
                compact_candidates.append(
                    {
                        "relative_path": c.get("relative_path"),
                        "filename": c.get("filename"),
                        "format": c.get("format"),
                        "size_bytes": c.get("size_bytes"),
                        "columns": c.get("columns", [])[:80],
                        "path_parts": c.get("path_parts", []),
                    }
                )

            system_prompt = (
                "You are a scientific data curator specializing in "
                "artifact grounding for executable dataset validation.\n\n"
                "Your task is to map LOGICAL dataset files inferred from "
                "documentation to PHYSICAL files in a downloaded repository.\n\n"
                "Rules:\n"
                "- Use only the provided candidate_files.\n"
                "- Do NOT invent paths.\n"
                "- Prefer exact filename or file pattern matches.\n"
                "- Prefer extension/format matches.\n"
                "- Use column/header overlap when available.\n"
                "- Prefer actual data files over documentation, manifests, "
                "generated outputs, figures, or code files.\n"
                "- If no good physical match exists, use grounding_status='unresolved'.\n"
                "- If multiple plausible files exist, use grounding_status='ambiguous'.\n"
                "- Return JSON strictly following the required schema."
            )

            user_prompt = f"""
Article ID
----------------
{article_id}

Required output schema
----------------
{self.get_output_schema()}

Logical dataset files
----------------
{json.dumps(compact_logical_files, ensure_ascii=False, indent=2)}

Physical candidate files
----------------
{json.dumps(compact_candidates, ensure_ascii=False, indent=2)}

Output requirements
----------------
- Return one resolution object for each logical dataset file.
- resolved_relative_path must be null unless grounding_status is "resolved".
- resolved_relative_path must exactly match one candidate_files relative_path.
- confidence should reflect grounding certainty.
- reason should be concise and evidence-based.
"""

            raw_response = self.llm.generate(
                system_prompt,
                user_prompt,
            )

            parsed = self.llm.parse_json_response(
                raw_response,
            )

            parsed["inventory_summary"] = {
                "candidate_count": inventory.get("candidate_count", 0),
                "inventory_path": str(inventory_output_path),
                "dataset_structure_path": str(dataset_structure_path),
            }

            return self.prepare_result(
                parsed,
                article_id,
            )

        except Exception as exc:
            return self.handle_error(
                exc,
                article_id,
            )
