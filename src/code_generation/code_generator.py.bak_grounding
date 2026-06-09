from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.code_generation.failure_taxonomy import (
    GEN_ACCESS_RESTRICTED,
    GEN_AMBIGUOUS_FILE_MAPPING,
    GEN_INVALID_DATASET_STRUCTURE,
    GEN_NO_DATASET_STRUCTURE,
    GEN_NO_DOWNLOADABLE_ARTIFACT,
    GEN_NO_FILES,
    GEN_NO_SUPPORTED_FORMAT,
    GEN_SCHEMA_TOO_WEAK,
    GenerationFailure,
)
from src.code_generation.file_selection import SelectedFile, select_primary_files
from src.code_generation.templates import write_all_templates
from src.utils.io import load_json, save_json


class CodeGenerator:
    """
    Generate a lightweight validation scaffold from dataset_structure.json.

    This stage only performs generation-time checks. It does not execute the
    generated code and does not classify runtime errors.
    """

    generated_version = "code_gen_v0.2.0"

    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def generate(
        self,
        *,
        article_id: str,
        dataset_structure_path: Path,
        artifact_root: Path,
        output_dir: Path,
    ) -> Dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)

        base_manifest: Dict[str, Any] = {
            "article_id": article_id,
            "generated_version": self.generated_version,
            "dataset_structure_path": str(dataset_structure_path),
            "artifact_root": str(artifact_root),
            "data_roots": [str(artifact_root)],
            "selected_primary_files": [],
            "generation_failure": None,
            "generation_warnings": [],
            "generation_notes": [],
        }

        if not dataset_structure_path.exists():
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_NO_DATASET_STRUCTURE,
                    detail="dataset_structure.json not found",
                ),
            )

        try:
            dataset_structure = load_json(dataset_structure_path)
        except Exception as exc:
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_INVALID_DATASET_STRUCTURE,
                    detail=f"failed to load dataset_structure.json: {type(exc).__name__}: {exc}",
                ),
            )

        result = dataset_structure.get("result")
        if not isinstance(result, dict):
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_INVALID_DATASET_STRUCTURE,
                    detail="dataset_structure.result is missing or not an object",
                ),
            )

        if result.get("error"):
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_INVALID_DATASET_STRUCTURE,
                    detail=f"dataset_structure extraction error: {result.get('error')}",
                ),
            )

        files = result.get("files")
        if not isinstance(files, list) or not files:
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_NO_FILES,
                    detail="result.files is empty or invalid",
                ),
            )

        selected = select_primary_files(files, top_k=self.top_k)
        if not selected:
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_NO_SUPPORTED_FORMAT,
                    detail="no supported tabular files found in dataset_structure",
                ),
            )

        strongest = selected[0]
        if not strongest.path and not strongest.file_pattern:
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_AMBIGUOUS_FILE_MAPPING,
                    detail="top selected file has neither path nor file_pattern",
                ),
            )

        artifact_manifest = artifact_root / "ARTIFACT_DOWNLOAD_MANIFEST.json"
        has_artifact_root = artifact_root.exists()
        has_artifact_manifest = artifact_manifest.exists()

        if not has_artifact_root:
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_NO_DOWNLOADABLE_ARTIFACT,
                    "detail": "artifact root does not exist; generated code may fail at execution time",
                }
            )
        elif not has_artifact_manifest:
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_NO_DOWNLOADABLE_ARTIFACT,
                    "detail": "artifact download manifest not found; generated code will use artifact root fallback search",
                }
            )

        if self._looks_access_restricted(result):
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_ACCESS_RESTRICTED,
                    "detail": "dataset appears to require credentialing, registration, or restricted access",
                }
            )

        if self._schema_too_weak(selected):
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_SCHEMA_TOO_WEAK,
                    "detail": "selected files have limited or missing expected column information",
                }
            )

        write_all_templates(output_dir, article_id)

        full_manifest = self._build_manifest(
            base_manifest=base_manifest,
            result=result,
            selected=selected,
            artifact_manifest=artifact_manifest if has_artifact_manifest else None,
        )

        save_json(full_manifest, output_dir / "generated_manifest.json")
        return full_manifest

    def _build_manifest(
        self,
        *,
        base_manifest: Dict[str, Any],
        result: Dict[str, Any],
        selected: List[SelectedFile],
        artifact_manifest: Optional[Path],
    ) -> Dict[str, Any]:
        manifest = dict(base_manifest)

        organization = result.get("organization") or {}
        dataset_identity = result.get("dataset_identity") or {}

        manifest.update(
            {
                "dataset_identity": dataset_identity,
                "organization_type": organization.get("type", "unknown") if isinstance(organization, dict) else "unknown",
                "structure_confidence": self._safe_float(result.get("structure_confidence")),
                "validation_targets": result.get("validation_targets", []),
                "execution_relevant_notes": result.get("execution_relevant_notes", []),
                "artifact_download_manifest_path": str(artifact_manifest) if artifact_manifest else None,
                "selected_primary_files": [item.to_dict() for item in selected],
                "generation_failure": None,
            }
        )

        manifest["generation_notes"].extend(
            [
                "Generated scaffold loads selected tabular files from artifact_root.",
                "Runtime file loading and validation errors are classified later by the execution stage.",
                "This generation stage only records pre-execution feasibility warnings.",
            ]
        )

        return manifest

    def _write_failure(
        self,
        output_dir: Path,
        manifest: Dict[str, Any],
        failure: GenerationFailure,
    ) -> Dict[str, Any]:
        manifest = dict(manifest)
        manifest["generation_failure"] = failure.to_dict()
        save_json(manifest, output_dir / "generated_manifest.json")
        return manifest

    def _looks_access_restricted(self, result: Dict[str, Any]) -> bool:
        notes = result.get("execution_relevant_notes", [])
        if not isinstance(notes, list):
            return False

        joined = "\n".join(str(x).lower() for x in notes)
        keywords = [
            "credential",
            "registration",
            "data use agreement",
            "dua",
            "restricted",
            "permission",
            "login",
            "account required",
        ]
        return any(keyword in joined for keyword in keywords)

    def _schema_too_weak(self, selected: List[SelectedFile]) -> bool:
        if not selected:
            return True

        with_columns = [item for item in selected if item.expected_columns]
        return len(with_columns) == 0

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0
