from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import csv
import json
import shutil


TABULAR_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".parquet",
}


DATA_TYPE_VALUES = {
    "numeric",
    "categorical",
    "string",
    "boolean",
    "datetime",
    "unknown",
}


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------


@dataclass
class Selected50Case:
    """
    One article-level workspace inside scidata_selected_50_v1.

    This object is the common path contract for the selected-50 workflow.
    It intentionally avoids the legacy run-name based path system.
    """

    article_id: str
    benchmark_root: Path

    case_dir: Path
    json_dir: Path
    artifact_dir: Path
    pdf_dir: Path
    notebooks_dir: Path

    readme_path: Path

    dataset_json_path: Path
    structured_data_path: Path
    scraped_repository_path: Path
    code_repository_path: Path

    dataset_structure_path: Path
    legacy_dataset_structure_path: Path

    refined_grounding_path: Path
    notebook_execution_path: Path
    curatability_report_path: Path
    human_annotations_path: Path

    effective_artifact_source: str
    effective_artifact_root: Path


@dataclass
class LogicalColumnClaim:
    column_id: str
    name: str
    data_type: str
    semantic_type: str
    description: str
    unit: Any
    required: Any


@dataclass
class LogicalFileClaim:
    logical_file_id: str
    logical_name: str
    documented_path_or_pattern: str
    expected_format: str
    schema_type: str
    role: str
    source: str
    columns: List[LogicalColumnClaim]
    raw: Dict[str, Any]


@dataclass
class PhysicalArtifactFile:
    relative_path: str
    absolute_path: str
    name: str
    stem: str
    suffix: str
    size_bytes: int
    is_tabular_candidate: bool


# ---------------------------------------------------------------------
# Basic readers
# ---------------------------------------------------------------------


def read_json_if_exists(path: Path) -> Dict[str, Any]:
    """
    Local JSON loader.

    We define this here instead of assuming src.utils.io has load_json,
    because the old runner only showed save_json and write_manifest.
    """
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "_read_error": str(exc),
            "_path": str(path),
        }


def read_text_if_exists(path: Path, max_chars: int = 20000) -> str:
    if not path.exists():
        return ""

    try:
        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )[:max_chars]
    except Exception:
        return ""


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def is_unknown(value: Any) -> bool:
    if value is None:
        return True

    text = str(value).strip().lower()

    return text in {
        "",
        "unknown",
        "null",
        "none",
        "n/a",
        "na",
    }


def clean_str(value: Any, default: str = "unknown") -> str:
    if is_unknown(value):
        return default

    return str(value).strip()


# ---------------------------------------------------------------------
# Benchmark-level loading
# ---------------------------------------------------------------------


def load_selected_article_ids(benchmark_root: Path) -> List[str]:
    """
    Read selected_50_article_ids.txt.
    """
    ids_path = benchmark_root / "selected_50_article_ids.txt"

    if not ids_path.exists():
        raise FileNotFoundError(f"Missing selected_50_article_ids.txt: {ids_path}")

    return [
        line.strip()
        for line in ids_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_effective_artifact_manifest(
    benchmark_root: Path,
) -> Dict[str, Dict[str, str]]:
    """
    Read effective_artifact_manifest.csv as article_id -> manifest row.
    """
    manifest_path = benchmark_root / "effective_artifact_manifest.csv"
    rows = read_csv_rows(manifest_path)

    if not rows:
        raise ValueError(f"Empty effective artifact manifest: {manifest_path}")

    if "article_id" not in rows[0]:
        raise ValueError(
            "effective_artifact_manifest.csv must contain article_id. "
            f"Columns: {list(rows[0].keys())}"
        )

    return {
        row["article_id"]: row
        for row in rows
        if row.get("article_id")
    }


def _first_existing_column(
    row: Dict[str, str],
    candidates: List[str],
) -> Optional[str]:
    for col in candidates:
        value = row.get(col)
        if value is not None and str(value).strip():
            return col
    return None


def _dir_has_files(path: Path) -> bool:
    return path.exists() and any(p.is_file() for p in path.rglob("*"))


def resolve_effective_artifact_root(
    benchmark_root: Path,
    article_id: str,
    manifest_row: Dict[str, str],
) -> tuple[Path, str]:
    """
    Resolve the effective artifact root for one article.

    Preferred:
      use effective_artifact_manifest.csv if it has a root/path column.

    Fallback:
      use the benchmark construction rule:
        figshare if present,
        else osf if present,
        else github.
    """

    case_dir = benchmark_root / article_id

    source_col = _first_existing_column(
        manifest_row,
        [
            "effective_artifact_source",
            "artifact_source",
            "effective_source",
            "source",
        ],
    )

    root_col = _first_existing_column(
        manifest_row,
        [
            "effective_artifact_root",
            "effective_root",
            "artifact_root",
            "root",
            "effective_artifact_path",
            "artifact_path",
        ],
    )

    source = (
        str(manifest_row[source_col]).strip()
        if source_col
        else "unknown"
    )

    if root_col:
        root = Path(str(manifest_row[root_col]).strip())
        if not root.is_absolute():
            root = benchmark_root / root
        return root, source

    figshare = case_dir / "artifact" / "figshare"
    osf = case_dir / "artifact" / "osf"
    github = case_dir / "artifact" / "github"

    if _dir_has_files(figshare):
        return figshare, "figshare"

    if _dir_has_files(osf):
        return osf, "osf"

    return github, "github"


def load_selected50_case(
    benchmark_root: Path,
    article_id: str,
    effective_manifest: Dict[str, Dict[str, str]],
) -> Selected50Case:
    """
    Build a Selected50Case object from benchmark_root + article_id.
    """
    benchmark_root = benchmark_root.resolve()

    if article_id not in effective_manifest:
        raise KeyError(
            f"{article_id} not found in effective_artifact_manifest.csv"
        )

    case_dir = benchmark_root / article_id
    json_dir = case_dir / "json"
    artifact_dir = case_dir / "artifact"
    pdf_dir = case_dir / "pdf"
    notebooks_dir = case_dir / "notebooks"
    notebooks_dir.mkdir(parents=True, exist_ok=True)

    effective_root, effective_source = resolve_effective_artifact_root(
        benchmark_root=benchmark_root,
        article_id=article_id,
        manifest_row=effective_manifest[article_id],
    )

    return Selected50Case(
        article_id=article_id,
        benchmark_root=benchmark_root,

        case_dir=case_dir,
        json_dir=json_dir,
        artifact_dir=artifact_dir,
        pdf_dir=pdf_dir,
        notebooks_dir=notebooks_dir,

        readme_path=case_dir / "README.md",

        dataset_json_path=json_dir / "dataset.json",
        structured_data_path=json_dir / "structured_data.json",
        scraped_repository_path=json_dir / "scraped_repository.json",
        code_repository_path=json_dir / "code_repository.json",

        dataset_structure_path=json_dir / "dataset_structure.json",
        legacy_dataset_structure_path=(
            json_dir / "dataset_structure_legacy_run4293.json"
        ),

        refined_grounding_path=json_dir / "refined_artifact_grounding.json",
        notebook_execution_path=json_dir / "notebook_execution.json",
        curatability_report_path=json_dir / "curatability_report.json",
        human_annotations_path=json_dir / "human_annotations.json",

        effective_artifact_source=effective_source,
        effective_artifact_root=effective_root,
    )


def load_all_selected50_cases(
    benchmark_root: Path,
    max_articles: Optional[int] = None,
    article_id: Optional[str] = None,
) -> List[Selected50Case]:
    """
    Convenience loader for runners.
    """
    effective_manifest = load_effective_artifact_manifest(benchmark_root)

    if article_id:
        article_ids = [article_id]
    else:
        article_ids = load_selected_article_ids(benchmark_root)

    if max_articles is not None:
        article_ids = article_ids[:max_articles]

    return [
        load_selected50_case(
            benchmark_root=benchmark_root,
            article_id=aid,
            effective_manifest=effective_manifest,
        )
        for aid in article_ids
    ]


# ---------------------------------------------------------------------
# Legacy schema backup
# ---------------------------------------------------------------------


def backup_legacy_dataset_structure(
    case: Selected50Case,
    overwrite_backup: bool = False,
) -> bool:
    """
    Backup copied run_4293 dataset_structure.json.

    This is optional. If we decide not to run schema refinement, this function
    may not be needed, but it remains useful for provenance.
    """
    src = case.dataset_structure_path
    dst = case.legacy_dataset_structure_path

    if not src.exists():
        return False

    if dst.exists() and not overwrite_backup:
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


# ---------------------------------------------------------------------
# Logical schema loading
# ---------------------------------------------------------------------


def unwrap_dataset_structure(schema_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Existing dataset_structure.json is usually BaseExtractor output:

      {
        "status": "success",
        "article_id": "...",
        "result": {...}
      }

    This function also supports raw schema dictionaries.
    """
    if not isinstance(schema_obj, dict):
        return {}

    if isinstance(schema_obj.get("result"), dict):
        return schema_obj["result"]

    return schema_obj


def normalize_data_type(value: Any) -> str:
    text = clean_str(value, default="unknown").lower()

    if text in DATA_TYPE_VALUES:
        return text

    return "unknown"


def normalize_semantic_type(value: Any) -> str:
    """
    semantic_type should describe dataset role, not machine data type.

    Example:
      data_type = string
      semantic_type = participant_identifier

    If an old schema used data types as semantic types, normalize to unknown.
    """
    text = clean_str(value, default="unknown")

    if text.lower() in DATA_TYPE_VALUES:
        return "unknown"

    return text


def normalize_required(value: Any) -> Any:
    if isinstance(value, bool):
        return value

    if value is None:
        return "unknown"

    text = str(value).strip().lower()

    if text == "true":
        return True

    if text == "false":
        return False

    if text in {"unknown", "", "none", "null", "n/a", "na"}:
        return "unknown"

    return value


def extract_columns_from_legacy_file(
    logical_file_id: str,
    file_obj: Dict[str, Any],
) -> List[LogicalColumnClaim]:
    structure = file_obj.get("structure") or {}
    columns = structure.get("columns") or {}

    output: List[LogicalColumnClaim] = []

    if isinstance(columns, dict):
        iterable = list(columns.items())

        for idx, (column_name, column_info) in enumerate(iterable, start=1):
            if not column_name:
                continue

            if not isinstance(column_info, dict):
                column_info = {}

            output.append(
                LogicalColumnClaim(
                    column_id=f"{logical_file_id}_col_{idx:03d}",
                    name=str(column_name),
                    data_type=normalize_data_type(
                        column_info.get("data_type", "unknown")
                    ),
                    semantic_type=normalize_semantic_type(
                        column_info.get("semantic_type", "unknown")
                    ),
                    description=clean_str(
                        column_info.get("description", "unknown")
                    ),
                    unit=column_info.get("unit"),
                    required=normalize_required(
                        column_info.get("required", "unknown")
                    ),
                )
            )

    elif isinstance(columns, list):
        for idx, column_info in enumerate(columns, start=1):
            if not isinstance(column_info, dict):
                continue

            column_name = column_info.get("name")
            if not column_name:
                continue

            output.append(
                LogicalColumnClaim(
                    column_id=f"{logical_file_id}_col_{idx:03d}",
                    name=str(column_name),
                    data_type=normalize_data_type(
                        column_info.get("data_type", "unknown")
                    ),
                    semantic_type=normalize_semantic_type(
                        column_info.get("semantic_type", "unknown")
                    ),
                    description=clean_str(
                        column_info.get("description", "unknown")
                    ),
                    unit=column_info.get("unit"),
                    required=normalize_required(
                        column_info.get("required", "unknown")
                    ),
                )
            )

    return output


def get_documented_path_or_pattern(file_obj: Dict[str, Any]) -> str:
    for key in ["file_pattern", "path", "documented_path_or_pattern"]:
        value = file_obj.get(key)
        if not is_unknown(value):
            return str(value).strip()

    return "unknown"


def get_expected_format(file_obj: Dict[str, Any]) -> str:
    for key in ["format", "expected_format"]:
        value = file_obj.get(key)
        if not is_unknown(value):
            return str(value).strip().lower()

    return "unknown"


def get_schema_type(file_obj: Dict[str, Any]) -> str:
    value = file_obj.get("schema_type")

    if is_unknown(value):
        return "unknown"

    return str(value).strip().lower()


def get_schema_files(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Support both old-style files and future logical_files if needed.
    """
    files = schema.get("files")

    if isinstance(files, list):
        return [
            f for f in files
            if isinstance(f, dict)
        ]

    logical_files = schema.get("logical_files")

    if isinstance(logical_files, list):
        converted = []

        for f in logical_files:
            if not isinstance(f, dict):
                continue

            converted.append(
                {
                    "logical_name": f.get("logical_name"),
                    "file_pattern": f.get("documented_path_or_pattern"),
                    "format": f.get("expected_format"),
                    "schema_type": f.get("schema_type"),
                    "role": f.get("role"),
                    "source": f.get("evidence_source", "mixed"),
                    "path": f.get("documented_path_or_pattern"),
                    "structure": {
                        "columns": {
                            c.get("name"): c
                            for c in f.get("columns", [])
                            if isinstance(c, dict) and c.get("name")
                        }
                    },
                }
            )

        return converted

    return []


def load_logical_claims(case: Selected50Case) -> Dict[str, Any]:
    """
    Load documentation-derived logical claims from dataset_structure.json.

    This function is effectively the schema adapter, but kept inside
    benchmark_loader.py because all selected-50 modules need it.

    It does NOT inspect artifact inventory.
    """
    schema_obj = read_json_if_exists(case.dataset_structure_path)
    schema = unwrap_dataset_structure(schema_obj)

    raw_files = get_schema_files(schema)

    logical_files: List[LogicalFileClaim] = []

    for idx, file_obj in enumerate(raw_files, start=1):
        logical_file_id = f"lf_{idx:03d}"

        columns = extract_columns_from_legacy_file(
            logical_file_id=logical_file_id,
            file_obj=file_obj,
        )

        logical_files.append(
            LogicalFileClaim(
                logical_file_id=logical_file_id,
                logical_name=clean_str(
                    file_obj.get("logical_name", "unknown")
                ),
                documented_path_or_pattern=get_documented_path_or_pattern(file_obj),
                expected_format=get_expected_format(file_obj),
                schema_type=get_schema_type(file_obj),
                role=clean_str(file_obj.get("role", "unknown")),
                source=clean_str(file_obj.get("source", "unknown")),
                columns=columns,
                raw=file_obj,
            )
        )

    return {
        "article_id": case.article_id,
        "schema_path": str(case.dataset_structure_path),
        "schema_status": schema_obj.get("status", "raw_or_unknown"),
        "structure_confidence": schema.get("structure_confidence", "unknown"),
        "sample_or_record_unit": schema.get("sample_or_record_unit", "unknown"),
        "spatial_temporal_coverage": schema.get(
            "spatial_temporal_coverage",
            {},
        ),
        "validation_targets": schema.get("validation_targets", []),
        "execution_relevant_notes": schema.get(
            "execution_relevant_notes",
            [],
        ),
        "logical_files": [
            logical_file_to_dict(f)
            for f in logical_files
        ],
        "summary": summarize_logical_claims(logical_files),
    }


def logical_column_to_dict(col: LogicalColumnClaim) -> Dict[str, Any]:
    return {
        "column_id": col.column_id,
        "name": col.name,
        "data_type": col.data_type,
        "semantic_type": col.semantic_type,
        "description": col.description,
        "unit": col.unit,
        "required": col.required,
    }


def logical_file_to_dict(file_claim: LogicalFileClaim) -> Dict[str, Any]:
    return {
        "logical_file_id": file_claim.logical_file_id,
        "logical_name": file_claim.logical_name,
        "documented_path_or_pattern": file_claim.documented_path_or_pattern,
        "expected_format": file_claim.expected_format,
        "schema_type": file_claim.schema_type,
        "role": file_claim.role,
        "source": file_claim.source,
        "columns": [
            logical_column_to_dict(c)
            for c in file_claim.columns
        ],
        "num_columns": len(file_claim.columns),
        "raw": file_claim.raw,
    }


def summarize_logical_claims(
    logical_files: List[LogicalFileClaim],
) -> Dict[str, Any]:
    num_files = len(logical_files)

    num_with_path_or_pattern = sum(
        1 for f in logical_files
        if not is_unknown(f.documented_path_or_pattern)
    )

    num_with_format = sum(
        1 for f in logical_files
        if not is_unknown(f.expected_format)
    )

    num_tabular_claims = sum(
        1 for f in logical_files
        if (
            f.expected_format in {"csv", "tsv", "xlsx", "xls", "parquet"}
            or f.schema_type == "tabular"
        )
    )

    num_with_columns = sum(
        1 for f in logical_files
        if len(f.columns) > 0
    )

    total_columns = sum(
        len(f.columns)
        for f in logical_files
    )

    return {
        "num_logical_files": num_files,
        "num_files_with_path_or_pattern": num_with_path_or_pattern,
        "num_files_with_format": num_with_format,
        "num_tabular_logical_claims": num_tabular_claims,
        "num_files_with_columns": num_with_columns,
        "total_documented_columns": total_columns,
    }


# ---------------------------------------------------------------------
# Physical artifact loading
# ---------------------------------------------------------------------


def list_effective_artifact_files(
    case: Selected50Case,
    max_files: int = 5000,
) -> List[Dict[str, Any]]:
    """
    Inventory files under effective_artifact_root only.

    This function is intended for grounding, preview, notebook generation,
    and scoring.

    Important:
      Do not scan the whole artifact/ directory, because many cases have
      multiple sources such as figshare, github, and original_external_archives.
      The selected-50 workflow should use effective_artifact_root as the
      primary artifact root.
    """
    root = case.effective_artifact_root
    files: List[Dict[str, Any]] = []

    if not root.exists():
        return files

    for p in root.rglob("*"):
        if not p.is_file():
            continue

        suffix = p.suffix.lower()

        files.append(
            {
                "relative_path": str(p.relative_to(root)),
                "absolute_path": str(p),
                "name": p.name,
                "stem": p.stem,
                "suffix": suffix,
                "size_bytes": p.stat().st_size,
                "is_tabular_candidate": suffix in TABULAR_SUFFIXES,
            }
        )

        if len(files) >= max_files:
            break

    return files


def physical_file_to_dataclass(
    file_obj: Dict[str, Any],
) -> PhysicalArtifactFile:
    return PhysicalArtifactFile(
        relative_path=str(file_obj.get("relative_path", "")),
        absolute_path=str(file_obj.get("absolute_path", "")),
        name=str(file_obj.get("name", "")),
        stem=str(file_obj.get("stem", "")),
        suffix=str(file_obj.get("suffix", "")),
        size_bytes=int(file_obj.get("size_bytes", 0) or 0),
        is_tabular_candidate=bool(file_obj.get("is_tabular_candidate", False)),
    )


def load_physical_inventory(
    case: Selected50Case,
    max_files: int = 5000,
) -> Dict[str, Any]:
    """
    Load observed physical artifact inventory from effective_artifact_root.

    This is the physical side of the claim-vs-artifact comparison.
    """
    files = list_effective_artifact_files(
        case,
        max_files=max_files,
    )

    return {
        "article_id": case.article_id,
        "effective_artifact_source": case.effective_artifact_source,
        "effective_artifact_root": str(case.effective_artifact_root),
        "effective_artifact_root_exists": case.effective_artifact_root.exists(),
        "num_files": len(files),
        "num_tabular_candidates": sum(
            1 for f in files
            if f.get("is_tabular_candidate")
        ),
        "files": files,
    }


def list_all_artifact_sources(case: Selected50Case) -> Dict[str, Any]:
    """
    Optional source-level overview for provenance and warning generation.

    This does not replace effective_artifact_root. It is useful for detecting
    multiple-source situations, such as figshare + github, but grounding should
    still use the effective artifact root as primary.
    """
    sources = {}

    for source_name in [
        "figshare",
        "osf",
        "github",
        "zenodo",
        "original_external_archives",
    ]:
        source_dir = case.artifact_dir / source_name

        if source_dir.exists():
            files = [
                p
                for p in source_dir.rglob("*")
                if p.is_file()
            ]

            sources[source_name] = {
                "path": str(source_dir),
                "exists": True,
                "num_files": len(files),
                "num_tabular_candidates": sum(
                    1 for p in files
                    if p.suffix.lower() in TABULAR_SUFFIXES
                ),
                "is_effective_source": (
                    source_name == case.effective_artifact_source
                ),
            }

        else:
            sources[source_name] = {
                "path": str(source_dir),
                "exists": False,
                "num_files": 0,
                "num_tabular_candidates": 0,
                "is_effective_source": False,
            }

    return sources


# ---------------------------------------------------------------------
# Grounding input assembly
# ---------------------------------------------------------------------


def load_grounding_inputs(
    case: Selected50Case,
    max_artifact_files: int = 5000,
) -> Dict[str, Any]:
    """
    Load the two evidence layers needed for physical grounding.

    logical_claims:
      documentation-derived claims from dataset_structure.json

    physical_inventory:
      observed files under effective_artifact_root

    Grounding compares these two layers. It should not modify either layer.
    """
    return {
        "article_id": case.article_id,
        "case_dir": str(case.case_dir),
        "logical_claims": load_logical_claims(case),
        "physical_inventory": load_physical_inventory(
            case,
            max_files=max_artifact_files,
        ),
        "artifact_sources_overview": list_all_artifact_sources(case),
    }


# ---------------------------------------------------------------------
# Optional all-JSON bundle for diagnostics / provenance
# ---------------------------------------------------------------------


def load_case_json_bundle(
    case: Selected50Case,
) -> Dict[str, Any]:
    """
    Load all available JSON files for diagnostics / provenance.

    Physical grounding should primarily use:
      - dataset_structure.json
      - effective artifact inventory

    Other JSON files are useful for debugging and reporting, but should not
    override the documentation-derived logical claims in dataset_structure.json.
    """
    validation_dir = case.json_dir / "validation"

    return {
        "article_id": case.article_id,
        "dataset_json": read_json_if_exists(case.dataset_json_path),
        "structured_data_json": read_json_if_exists(case.structured_data_path),
        "scraped_repository_json": read_json_if_exists(case.scraped_repository_path),
        "code_repository_json": read_json_if_exists(case.code_repository_path),
        "dataset_structure_json": read_json_if_exists(case.dataset_structure_path),
        "legacy_dataset_structure_json": read_json_if_exists(
            case.legacy_dataset_structure_path
        ),
        "artifact_download_manifest_json": read_json_if_exists(
            case.json_dir / "ARTIFACT_DOWNLOAD_MANIFEST.json"
        ),
        "dataset_url_validation_json": read_json_if_exists(
            validation_dir / "dataset_url_validation.json"
        ),
        "code_repository_validation_json": read_json_if_exists(
            validation_dir / "code_repository_validation.json"
        ),
    }


# ---------------------------------------------------------------------
# Backward-compatible context helpers
# ---------------------------------------------------------------------


def build_documentation_context(
    case: Selected50Case,
) -> Dict[str, Any]:
    """
    Documentation/logical side.

    Kept for compatibility with earlier discussion. New code should prefer
    load_logical_claims(case) if it needs normalized schema claims.
    """
    return {
        "article_id": case.article_id,
        "context_type": "logical_claims",
        "logical_claims": load_logical_claims(case),
    }


def build_grounding_context(
    case: Selected50Case,
    max_artifact_files: int = 5000,
) -> Dict[str, Any]:
    """
    Claim-vs-artifact grounding context.
    """
    return load_grounding_inputs(
        case,
        max_artifact_files=max_artifact_files,
    )


def build_case_context(
    case: Selected50Case,
    include_artifact_inventory: bool = False,
    max_artifact_files: int = 5000,
) -> Dict[str, Any]:
    """
    Backward-compatible alias.

    If include_artifact_inventory=False:
      return logical/documentation side only.

    If include_artifact_inventory=True:
      return logical claims + physical inventory for grounding.
    """
    if include_artifact_inventory:
        return build_grounding_context(
            case,
            max_artifact_files=max_artifact_files,
        )

    return build_documentation_context(case)
