from __future__ import annotations

from typing import Any, Dict, List

from src.context.context_builder import ContextBuilder
from src.extraction.base_extractor import BaseExtractor
from src.utils.config import LLM_CONFIG
from src.utils.llm_client import get_llm_client


class DatasetStructureExtractor(BaseExtractor):
    """
    Dataset Structure Extractor

    Responsibilities:
    - Infer dataset organization structure
    - Infer logical data files/groups
    - Infer formats and schema types
    - Infer semantic fields when documented
    - Attach provenance
    - Support repository-aware extraction

    This extractor focuses on structural understanding
    rather than data downloading or execution.
    """

    def __init__(self):
        super().__init__("dataset_structure")

        self.context_builder = ContextBuilder(
            max_tokens=LLM_CONFIG.get("safe_prompt_budget", 64000),
            max_repository_tokens=8000,
        )

        self.llm = get_llm_client()

    # ------------------------------------------------------------------
    # Context strategy
    # ------------------------------------------------------------------

    def get_context_strategy(self) -> str:
        """
        Dataset structure inference benefits from broad context.

        Full paper + repository context may be auto-upgraded
        when within token budget.
        """
        return "section_focused_context"

    def get_section_priority(self) -> List[str]:
        """
        Prioritize sections likely to contain:
        - dataset organization
        - file descriptions
        - schema details
        - repository metadata
        """
        return [
            "Data Records",
            "Data Availability",
            "Dataset",
            "Data Description",
            "Methods",
            "Supplementary",
            "README",
            "Codebook",
            "Repository",
            "Scraped Repository",
        ]

    def get_keywords(self) -> List[str]:
        return [
            ".csv",
            ".tsv",
            ".xlsx",
            ".json",
            ".jsonl",
            ".parquet",
            ".h5",
            ".hdf5",
            ".nc",
            "table",
            "column",
            "field",
            "variable",
            "schema",
            "codebook",
            "metadata",
            "directory",
            "folder",
            "per-subject",
            "per-sample",
            "API",
            "endpoint",
        ]

    # ------------------------------------------------------------------
    # Output schema
    # ------------------------------------------------------------------

    def get_output_schema(self) -> Dict[str, Any]:
        return {
            "dataset_identity": {
                "dataset_name": "string",
                "dataset_version": "string | unknown",
                "dataset_domain": "string | unknown",
            },
            "organization": {
                "type": (
                    "flat | hierarchical | sharded | "
                    "api_based | mixed | unknown"
                ),
                "description": "string",
            },
            "files": [
                {
                    "logical_name": "string",
                    "file_pattern": "string | unknown",
                    "format": (
                        "csv | tsv | xlsx | json | jsonl | "
                        "parquet | netcdf | hdf5 | text | "
                        "binary | image | unknown"
                    ),
                    "schema_type": (
                        "tabular | hierarchical | "
                        "array | text | image | unknown"
                    ),
                    "role": (
                        "primary_data | derived_data | "
                        "metadata | annotation | unknown"
                    ),
                    "source": (
                        "paper | structured_data.json | "
                        "scraped_repository.json"
                    ),
                    "path": "string | unknown",
                    "structure": {
                        "columns": {
                            "<column_name>": {
                                "data_type": (
                                    "numeric | categorical | "
                                    "string | boolean | "
                                    "datetime | unknown"
                                ),
                                "semantic_type": "string",
                                "description": "string",
                                "unit": "string | null",
                                "required": "boolean",
                            }
                        }
                    },
                }
            ],
            "sample_or_record_unit": "string | unknown",
            "spatial_temporal_coverage": {
                "spatial": "string | unknown",
                "temporal": "string | unknown",
            },
            "validation_targets": [
                "string"
            ],
            "execution_relevant_notes": [
                "string"
            ],
            "structure_confidence": "float",
        }

    # ------------------------------------------------------------------
    # Main extraction logic
    # ------------------------------------------------------------------

    def extract(
        self,
        article_id: str,
        article_result: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            # ----------------------------------------------------------
            # 1. Build context
            # ----------------------------------------------------------

            ctx = self.context_builder.build_context(
                article_id=article_id,
                strategy=self.get_context_strategy(),
                section_priority=self.get_section_priority(),
                keywords=self.get_keywords(),
            )

            # ----------------------------------------------------------
            # 2. System prompt
            # ----------------------------------------------------------

            system_prompt = (
                "You are a scientific data curator specializing in "
                "dataset structure inference.\n\n"

                "Your task is to infer the STRUCTURAL and SEMANTIC "
                "organization of datasets described in scientific "
                "papers and associated repository documentation.\n\n"

                "Rules:\n"
                "- Focus on FILE-LEVEL and ORGANIZATION-LEVEL structure.\n"
                "- Do NOT assume the dataset is downloadable.\n"
                "- Do NOT invent files, columns, formats, or APIs.\n"
                "- Use logical file groups when filenames are unclear.\n"
                "- Prefer conservative extraction.\n"
                "- Unknown is acceptable.\n"
                "- Partial schema extraction is acceptable.\n"
                "- Repository documentation may supplement the paper.\n"
                "- structure_confidence must reflect overall certainty.\n\n"

                "Return JSON strictly following the required schema."
            )

            # ----------------------------------------------------------
            # 3. User prompt
            # ----------------------------------------------------------

            user_prompt = f"""
Context
----------------
{ctx.content}

Required schema
----------------
{self.get_output_schema()}

Extraction notes
----------------
- Only include files or structures explicitly mentioned
  or strongly implied by evidence.

- Prefer logical file groups over hallucinated filenames.

- Leave columns empty if no schema is described.

- Infer validation_targets conservatively.

- execution_relevant_notes should contain practical
  execution-related observations such as:
    - compressed archives
    - API access
    - credentialed access
    - unusual formats
    - hierarchical layouts
    - large-scale sharding

- Do NOT exhaustively reconstruct the full data dictionary.

- Extract at most 8 logical files or file groups.
- For each file, extract at most 5 representative columns.

- Prioritize structurally important fields such as:
    - identifiers
    - timestamps
    - primary measurements
    - labels
    - coordinates
    - target variables
    - split variables
    - units

- Prefer concise structure summaries over exhaustive
  schema reconstruction.
"""

            # ----------------------------------------------------------
            # 4. LLM call
            # ----------------------------------------------------------

            raw_response = self.llm.generate(
                system_prompt,
                user_prompt,
            )

            parsed = self.llm.parse_json_response(raw_response)

            # ----------------------------------------------------------
            # 5. Limit schema size
            # ----------------------------------------------------------

            parsed = self._limit_schema_size(parsed)

            # ----------------------------------------------------------
            # 6. Attach context trace
            # ----------------------------------------------------------

            parsed["context_summary"] = ctx.trace.__dict__

            # ----------------------------------------------------------
            # 7. Post-normalization
            # ----------------------------------------------------------

            for f in parsed.get("files", []):
                if not f.get("source"):
                    f["source"] = self._infer_source(ctx)

                if not f.get("path"):
                    f["path"] = "unknown"

            # ----------------------------------------------------------
            # 8. Prepare standardized result
            # ----------------------------------------------------------

            return self.prepare_result(parsed, article_id)

        except Exception as exc:
            return self.handle_error(exc, article_id)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _infer_source(self, ctx) -> str:
        """
        Heuristic source inference.

        If repository content contributed to the context,
        prefer scraped_repository.json.
        """
        for sec in ctx.trace.sections_used:
            if "REPOSITORY" in sec:
                return "scraped_repository.json"

        return "structured_data.json"

    def _limit_schema_size(
        self,
        parsed: Dict[str, Any],
        max_files: int = 8,
        max_columns_per_file: int = 5,
    ) -> Dict[str, Any]:
        """
        Limit schema size to avoid:
        - token explosion
        - oversized JSON outputs
        - exhaustive dictionary reconstruction

        The goal is validation-oriented structural extraction,
        not full archival schema recovery.
        """

        files = parsed.get("files", [])

        if isinstance(files, list) and len(files) > max_files:
            parsed["files"] = files[:max_files]

        for f in parsed.get("files", []):
            structure = f.get("structure", {})
            columns = structure.get("columns", {})

            if (
                isinstance(columns, dict)
                and len(columns) > max_columns_per_file
            ):
                structure["columns"] = dict(
                    list(columns.items())[:max_columns_per_file]
                )

                f["structure"] = structure

        return parsed
