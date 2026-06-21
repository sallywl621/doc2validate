from __future__ import annotations

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

    C0 behavior:
    - Select logical dataset files from dataset_structure.json.
    - Generated runtime loader searches artifact_root heuristically.

    C1 behavior:
    - If artifact_grounding/{article_id}/grounding_manifest.json exists,
      use resolved_relative_path from artifact grounding.
    - Resolved logical files are grounded to physical files before execution.
    - Ambiguous/unresolved logical files are not allowed to fall back to
      arbitrary extension-based matching.
    """

    generated_version = "code_gen_v0.3.0_grounding"

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
                    detail=(
                        "failed to load dataset_structure.json: "
                        f"{type(exc).__name__}: {exc}"
                    ),
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
                    detail=(
                        "dataset_structure extraction error: "
                        f"{result.get('error')}"
                    ),
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

        selected_raw = select_primary_files(
            files,
            top_k=self.top_k,
        )

        if not selected_raw:
            return self._write_failure(
                output_dir,
                base_manifest,
                GenerationFailure(
                    category=GEN_NO_SUPPORTED_FORMAT,
                    detail="no supported tabular files found in dataset_structure",
                ),
            )

        strongest = selected_raw[0]

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
                    "detail": (
                        "artifact root does not exist; generated code may fail "
                        "at execution time"
                    ),
                }
            )

        elif not has_artifact_manifest:
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_NO_DOWNLOADABLE_ARTIFACT,
                    "detail": (
                        "artifact download manifest not found; generated code "
                        "will use artifact root fallback search"
                    ),
                }
            )

        if self._looks_access_restricted(result):
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_ACCESS_RESTRICTED,
                    "detail": (
                        "dataset appears to require credentialing, registration, "
                        "or restricted access"
                    ),
                }
            )

        if self._schema_too_weak(selected_raw):
            base_manifest["generation_warnings"].append(
                {
                    "category": GEN_SCHEMA_TOO_WEAK,
                    "detail": (
                        "selected files have limited or missing expected column "
                        "information"
                    ),
                }
            )

        grounding_manifest_path = self._infer_grounding_manifest_path(
            output_dir=output_dir,
            article_id=article_id,
        )

        grounding_by_logical_name = self._load_grounding_by_logical_name(
            grounding_manifest_path
        )

        selected = self._apply_artifact_grounding(
            selected=selected_raw,
            grounding_by_logical_name=grounding_by_logical_name,
            base_manifest=base_manifest,
            grounding_manifest_path=grounding_manifest_path,
        )

        write_all_templates(
            output_dir,
            article_id,
        )

        full_manifest = self._build_manifest(
            base_manifest=base_manifest,
            result=result,
            selected=selected,
            artifact_manifest=artifact_manifest if has_artifact_manifest else None,
            grounding_manifest_path=(
                grounding_manifest_path
                if grounding_manifest_path.exists()
                else None
            ),
        )

        save_json(
            full_manifest,
            output_dir / "generated_manifest.json",
        )

        return full_manifest

    # ------------------------------------------------------------------
    # Grounding helpers
    # ------------------------------------------------------------------

    def _infer_grounding_manifest_path(
        self,
        *,
        output_dir: Path,
        article_id: str,
    ) -> Path:
        """
        Infer run directory from:

        results/runs/{RUN_NAME}/generated_code/{article_id}

        so grounding path becomes:

        results/runs/{RUN_NAME}/artifact_grounding/{article_id}/grounding_manifest.json
        """

        run_dir = output_dir.parent.parent

        return (
            run_dir
            / "artifact_grounding"
            / article_id
            / "grounding_manifest.json"
        )

    def _load_grounding_by_logical_name(
        self,
        grounding_manifest_path: Path,
    ) -> Dict[str, Dict[str, Any]]:
        if not grounding_manifest_path.exists():
            return {}

        try:
            payload = load_json(
                grounding_manifest_path
            )

            resolutions = (
                payload
                .get("result", {})
                .get("resolutions", [])
            )

            out: Dict[str, Dict[str, Any]] = {}

            for item in resolutions:
                logical_name = item.get("logical_name")

                if not logical_name:
                    continue

                out[str(logical_name)] = item

            return out

        except Exception:
            return {}

    def _apply_artifact_grounding(
        self,
        *,
        selected: List[SelectedFile],
        grounding_by_logical_name: Dict[str, Dict[str, Any]],
        base_manifest: Dict[str, Any],
        grounding_manifest_path: Path,
    ) -> List[Dict[str, Any]]:
        """
        Convert SelectedFile objects to dicts and inject grounding decisions.

        Important:
        - resolved: use resolved_relative_path as the executable path.
        - ambiguous/unresolved: disable heuristic fallback by clearing
          path/file_pattern/format. This prevents false positive matching
          such as codebook.csv falling back to an unrelated CSV file.
        - no grounding manifest: keep C0 behavior.
        """

        grounded_selected: List[Dict[str, Any]] = []

        has_grounding_manifest = grounding_manifest_path.exists()

        if has_grounding_manifest:
            base_manifest["generation_notes"].append(
                "Artifact grounding manifest detected; generated code uses "
                "LLM-resolved physical paths when available."
            )

        else:
            base_manifest["generation_notes"].append(
                "No artifact grounding manifest detected; generated code uses "
                "heuristic runtime file search."
            )

        for item in selected:
            item_dict = item.to_dict()

            logical_name = item_dict.get("logical_name")
            original_path = item_dict.get("path")
            original_file_pattern = item_dict.get("file_pattern")
            original_format = item_dict.get("format")

            grounding = grounding_by_logical_name.get(
                str(logical_name)
            )

            if not grounding:
                item_dict["grounding_status"] = "not_available"
                item_dict["grounding_confidence"] = 0.0
                item_dict["grounding_reason"] = (
                    "No grounding resolution was available for this logical file."
                )

                grounded_selected.append(
                    item_dict
                )
                continue

            grounding_status = grounding.get(
                "grounding_status",
                "unresolved",
            )

            item_dict["grounding_status"] = grounding_status
            item_dict["grounding_confidence"] = grounding.get(
                "confidence",
                0.0,
            )
            item_dict["grounding_reason"] = grounding.get(
                "reason",
                "",
            )
            item_dict["original_path"] = original_path
            item_dict["original_file_pattern"] = original_file_pattern
            item_dict["original_format"] = original_format

            if grounding_status == "resolved":
                resolved_relative_path = grounding.get(
                    "resolved_relative_path"
                )

                if resolved_relative_path:
                    item_dict["path"] = resolved_relative_path
                    item_dict["file_pattern"] = Path(
                        resolved_relative_path
                    ).name

                    item_dict["generation_notes"] = [
                        "Using LLM artifact grounding resolved_relative_path."
                    ]

                else:
                    item_dict["path"] = None
                    item_dict["file_pattern"] = None
                    item_dict["format"] = ""
                    item_dict["generation_notes"] = [
                        "Grounding status was resolved but no resolved_relative_path "
                        "was provided; runtime loading disabled for this logical file."
                    ]

            elif grounding_status in {"ambiguous", "unresolved"}:
                # Disable fallback search to avoid false-positive artifact loading.
                item_dict["path"] = None
                item_dict["file_pattern"] = None
                item_dict["format"] = ""
                item_dict["generation_notes"] = [
                    "Artifact grounding did not resolve this logical file; "
                    "runtime fallback search disabled to avoid false-positive matching."
                ]

            else:
                item_dict["path"] = None
                item_dict["file_pattern"] = None
                item_dict["format"] = ""
                item_dict["generation_notes"] = [
                    f"Unknown grounding_status={grounding_status}; "
                    "runtime loading disabled for this logical file."
                ]

            grounded_selected.append(
                item_dict
            )

        return grounded_selected

    # ------------------------------------------------------------------
    # Manifest construction
    # ------------------------------------------------------------------

    def _build_manifest(
        self,
        *,
        base_manifest: Dict[str, Any],
        result: Dict[str, Any],
        selected: List[Dict[str, Any]],
        artifact_manifest: Optional[Path],
        grounding_manifest_path: Optional[Path],
    ) -> Dict[str, Any]:
        manifest = dict(base_manifest)

        organization = result.get("organization") or {}
        dataset_identity = result.get("dataset_identity") or {}

        manifest.update(
            {
                "dataset_identity": dataset_identity,
                "organization_type": (
                    organization.get("type", "unknown")
                    if isinstance(organization, dict)
                    else "unknown"
                ),
                "structure_confidence": self._safe_float(
                    result.get("structure_confidence")
                ),
                "validation_targets": result.get("validation_targets", []),
                "execution_relevant_notes": result.get(
                    "execution_relevant_notes",
                    [],
                ),
                "artifact_download_manifest_path": (
                    str(artifact_manifest)
                    if artifact_manifest
                    else None
                ),
                "artifact_grounding_manifest_path": (
                    str(grounding_manifest_path)
                    if grounding_manifest_path
                    else None
                ),
                "selected_primary_files": selected,
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

        save_json(
            manifest,
            output_dir / "generated_manifest.json",
        )

        return manifest

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    def _looks_access_restricted(
        self,
        result: Dict[str, Any],
    ) -> bool:
        notes = result.get("execution_relevant_notes", [])

        if not isinstance(notes, list):
            return False

        joined = "\n".join(
            str(x).lower()
            for x in notes
        )

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

        return any(
            keyword in joined
            for keyword in keywords
        )

    def _schema_too_weak(
        self,
        selected: List[SelectedFile],
    ) -> bool:
        if not selected:
            return True

        with_columns = [
            item
            for item in selected
            if item.expected_columns
        ]

        return len(with_columns) == 0

    def _safe_float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0
