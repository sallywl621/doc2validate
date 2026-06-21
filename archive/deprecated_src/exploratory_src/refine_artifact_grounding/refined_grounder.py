from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import fnmatch
import re


TABULAR_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".parquet",
}


RESOLVED_THRESHOLD = 0.80
CANDIDATE_THRESHOLD = 0.45
FORMAT_ONLY_SCORE = 0.20


def is_unknown(value: Any) -> bool:
    if value is None:
        return True

    text = str(value).strip().lower()

    return text in {
        "",
        "unknown",
        "none",
        "null",
        "n/a",
        "na",
    }


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def split_tokens(value: Any) -> set[str]:
    text = normalize_text(value)

    if not text:
        return set()

    return {
        t for t in text.split("_")
        if t and len(t) >= 2
    }


def get_expected_suffix(expected_format: Any) -> str:
    fmt = str(expected_format or "").strip().lower()

    if fmt in {"csv", "tsv", "xlsx", "xls", "parquet"}:
        return f".{fmt}"

    return ""


def physical_file_candidates(
    physical_inventory: Dict[str, Any],
) -> List[Dict[str, Any]]:
    files = physical_inventory.get("files") or []

    return [
        f for f in files
        if isinstance(f, dict)
    ]


def is_non_file_claim(logical_file: Dict[str, Any]) -> bool:
    """
    Detect logical claims that describe APIs/endpoints/streams rather than
    deposited physical files.

    These should not be treated as ordinary missing physical files.
    """
    text = " ".join(
        str(logical_file.get(k, "") or "")
        for k in [
            "logical_name",
            "documented_path_or_pattern",
            "expected_format",
            "schema_type",
            "role",
        ]
    ).lower()

    non_file_markers = [
        "api",
        "endpoint",
        "restful",
        "rest api",
        "web api",
        "data stream",
        "database query",
        "remote service",
    ]

    return any(marker in text for marker in non_file_markers)


def score_single_match(
    logical_file: Dict[str, Any],
    physical_file: Dict[str, Any],
) -> Tuple[float, str]:
    """
    Score one logical file claim against one physical file.

    This stage only uses filename/path/suffix evidence.
    It does not open files and does not inspect headers.
    """
    pattern = logical_file.get("documented_path_or_pattern", "unknown")
    logical_name = logical_file.get("logical_name", "unknown")
    expected_format = logical_file.get("expected_format", "unknown")

    rel_path = str(physical_file.get("relative_path", "") or "")
    name = str(physical_file.get("name", "") or "")
    stem = str(physical_file.get("stem", "") or "")
    suffix = str(physical_file.get("suffix", "") or "").lower()

    pattern_str = "" if is_unknown(pattern) else str(pattern).strip()
    pattern_name = Path(pattern_str).name if pattern_str else ""
    pattern_stem = Path(pattern_name).stem if pattern_name else ""

    expected_suffix = get_expected_suffix(expected_format)

    # 1. Exact relative path.
    if pattern_str and rel_path == pattern_str:
        return 1.00, "exact_relative_path"

    # 2. Exact basename.
    if pattern_name and name == pattern_name:
        return 0.95, "exact_basename"

    # 3. Glob pattern match.
    if pattern_str and any(ch in pattern_str for ch in ["*", "?", "["]):
        if fnmatch.fnmatch(rel_path, pattern_str) or fnmatch.fnmatch(name, pattern_str):
            return 0.90, "glob_pattern"

    # 4. Case-insensitive stem match.
    if pattern_stem and normalize_text(pattern_stem) == normalize_text(stem):
        return 0.85, "stem_match"

    # 5. Normalized basename match.
    if pattern_name and normalize_text(pattern_name) == normalize_text(name):
        return 0.80, "normalized_basename"

    # 6. One stem contains the other.
    norm_pattern_stem = normalize_text(pattern_stem)
    norm_stem = normalize_text(stem)

    if norm_pattern_stem and norm_stem:
        if norm_pattern_stem in norm_stem or norm_stem in norm_pattern_stem:
            return 0.65, "stem_contains"

    # 7. Token overlap between logical name / documented pattern and physical name.
    logical_tokens = split_tokens(logical_name) | split_tokens(pattern_stem)
    physical_tokens = split_tokens(stem)

    if logical_tokens and physical_tokens:
        overlap = logical_tokens & physical_tokens
        union = logical_tokens | physical_tokens
        jaccard = len(overlap) / len(union)

        if jaccard >= 0.50:
            return 0.60, "token_overlap_high"

        if jaccard >= 0.25:
            return 0.45, "token_overlap_low"

    # 8. Format-only match is too weak for grounding, but useful as evidence.
    if expected_suffix and suffix == expected_suffix:
        return FORMAT_ONLY_SCORE, "format_only"

    return 0.0, "no_match"


def score_logical_file_against_inventory(
    logical_file: Dict[str, Any],
    physical_files: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scored = []

    for physical_file in physical_files:
        score, match_type = score_single_match(
            logical_file=logical_file,
            physical_file=physical_file,
        )

        if score <= 0:
            continue

        scored.append(
            {
                "relative_path": physical_file.get("relative_path"),
                "absolute_path": physical_file.get("absolute_path"),
                "name": physical_file.get("name"),
                "stem": physical_file.get("stem"),
                "suffix": physical_file.get("suffix"),
                "size_bytes": physical_file.get("size_bytes"),
                "is_tabular_candidate": physical_file.get("is_tabular_candidate"),
                "match_score": round(score, 4),
                "match_type": match_type,
            }
        )

    scored.sort(
        key=lambda x: x["match_score"],
        reverse=True,
    )

    return scored


def determine_grounding_status(
    logical_file: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Determine final grounding status.

    Returns:
      status,
      matched_physical_files,
      candidate_physical_files,
      warnings
    """
    warnings = []

    logical_name = logical_file.get("logical_name", "unknown")
    pattern = logical_file.get("documented_path_or_pattern", "unknown")

    if is_non_file_claim(logical_file):
        warnings.append(
            {
                "warning_type": "unsupported_non_file_claim",
                "severity": "medium",
                "message": (
                    "This logical claim appears to describe an API, endpoint, "
                    "or data stream rather than a deposited physical file. "
                    "Physical file grounding cannot resolve it."
                ),
            }
        )

        return "unsupported_non_file_claim", [], [], warnings

    if is_unknown(logical_name) and is_unknown(pattern):
        warnings.append(
            {
                "warning_type": "ungroundable_logical_claim",
                "severity": "blocking",
                "message": (
                    "Logical file has neither logical_name nor "
                    "documented_path_or_pattern."
                ),
            }
        )

        return "ungroundable", [], [], warnings

    if not candidates:
        warnings.append(
            {
                "warning_type": "missing_physical_match",
                "severity": "high",
                "message": (
                    "No physical artifact candidate matched this logical file claim."
                ),
            }
        )

        return "missing", [], [], warnings

    top_score = candidates[0]["match_score"]
    candidate_files = candidates[:10]

    strong_candidates = [
        c for c in candidates
        if c["match_score"] >= CANDIDATE_THRESHOLD
    ]

    if not strong_candidates:
        format_only_candidates = [
            c for c in candidates
            if c["match_type"] == "format_only"
        ]

        if format_only_candidates:
            warnings.append(
                {
                    "warning_type": "missing_name_match_with_same_format_candidates",
                    "severity": "high",
                    "message": (
                        "Physical files with the expected format exist, but none "
                        "match the documented file name or pattern."
                    ),
                }
            )
        else:
            warnings.append(
                {
                    "warning_type": "missing_physical_match",
                    "severity": "high",
                    "message": (
                        "No physical artifact candidate matched this logical file "
                        "claim."
                    ),
                }
            )

        return "missing", [], candidate_files, warnings

    close_candidates = [
        c for c in strong_candidates
        if c["match_score"] >= top_score - 0.05
    ]

    if top_score >= RESOLVED_THRESHOLD and len(close_candidates) == 1:
        matched = [candidates[0]]
        return "resolved", matched, candidate_files, warnings

    if len(close_candidates) > 1:
        warnings.append(
            {
                "warning_type": "ambiguous_physical_match",
                "severity": "medium",
                "message": (
                    "Multiple physical artifacts match the logical file claim "
                    "with similar scores."
                ),
            }
        )

        return "ambiguous", close_candidates, candidate_files, warnings

    if top_score >= CANDIDATE_THRESHOLD:
        warnings.append(
            {
                "warning_type": "weak_physical_match",
                "severity": "medium",
                "message": (
                    "A possible physical artifact match was found, but the match "
                    "is weak and should be reviewed by a curator."
                ),
            }
        )

        return "weak_match", [candidates[0]], candidate_files, warnings

    warnings.append(
        {
            "warning_type": "missing_physical_match",
            "severity": "high",
            "message": (
                "No sufficiently strong physical artifact match was found."
            ),
        }
    )

    return "missing", [], candidate_files, warnings


def ground_one_logical_file(
    logical_file: Dict[str, Any],
    physical_files: List[Dict[str, Any]],
) -> Dict[str, Any]:
    candidates = score_logical_file_against_inventory(
        logical_file=logical_file,
        physical_files=physical_files,
    )

    status, matched_files, candidate_files, warnings = determine_grounding_status(
        logical_file=logical_file,
        candidates=candidates,
    )

    human_review_needed = status != "resolved" or len(warnings) > 0

    return {
        "logical_file_id": logical_file.get("logical_file_id"),
        "logical_name": logical_file.get("logical_name"),
        "documented_path_or_pattern": logical_file.get("documented_path_or_pattern"),
        "expected_format": logical_file.get("expected_format"),
        "schema_type": logical_file.get("schema_type"),
        "role": logical_file.get("role"),
        "num_documented_columns": len(logical_file.get("columns", []) or []),

        "grounding_status": status,
        "human_review_needed": human_review_needed,

        "matched_physical_files": matched_files,
        "candidate_physical_files": candidate_files,
        "warnings": warnings,
    }


def summarize_file_groundings(
    file_groundings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total = len(file_groundings)

    counts = {
        "resolved": 0,
        "ambiguous": 0,
        "weak_match": 0,
        "missing": 0,
        "ungroundable": 0,
        "unsupported_non_file_claim": 0,
    }

    for g in file_groundings:
        status = g.get("grounding_status", "ungroundable")

        if status not in counts:
            counts[status] = 0

        counts[status] += 1

    file_applicable_total = (
        total
        - counts.get("unsupported_non_file_claim", 0)
    )

    if file_applicable_total <= 0:
        grounding_score = 0.0
    else:
        grounding_score = (
            counts.get("resolved", 0)
            + 0.50 * counts.get("ambiguous", 0)
            + 0.25 * counts.get("weak_match", 0)
        ) / file_applicable_total

    warning_counts: Dict[str, int] = {}

    for g in file_groundings:
        for w in g.get("warnings", []):
            wtype = w.get("warning_type", "unknown")
            warning_counts[wtype] = warning_counts.get(wtype, 0) + 1

    return {
        "num_logical_files": total,
        "num_file_grounding_applicable": file_applicable_total,
        "num_resolved": counts.get("resolved", 0),
        "num_ambiguous": counts.get("ambiguous", 0),
        "num_weak_match": counts.get("weak_match", 0),
        "num_missing": counts.get("missing", 0),
        "num_ungroundable": counts.get("ungroundable", 0),
        "num_unsupported_non_file_claim": counts.get(
            "unsupported_non_file_claim",
            0,
        ),
        "num_human_review_needed": sum(
            1 for g in file_groundings
            if g.get("human_review_needed")
        ),
        "grounding_score": round(grounding_score, 4),
        "warning_counts": warning_counts,
    }


def generate_human_review_targets(
    file_groundings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    targets = []

    for g in file_groundings:
        if not g.get("human_review_needed"):
            continue

        status = g.get("grounding_status")

        if status == "missing":
            question = (
                "The documented logical file does not match any physical artifact "
                "by name or path. Should this claim be treated as missing, renamed, "
                "or mapped manually to another file?"
            )
            default_action = "needs_second_review"

        elif status == "ambiguous":
            question = (
                "Multiple physical files match this logical claim. Which file should "
                "be treated as the primary match?"
            )
            default_action = "modify_code"

        elif status == "weak_match":
            question = (
                "The best physical match is weak. Should the notebook use this file, "
                "or should the claim be marked unresolved?"
            )
            default_action = "needs_second_review"

        elif status == "ungroundable":
            question = (
                "The logical claim lacks enough documented information for grounding. "
                "Should supplementary information be requested?"
            )
            default_action = "request_materials"

        elif status == "unsupported_non_file_claim":
            question = (
                "This logical claim appears to describe an API, endpoint, or data "
                "stream rather than a deposited file. Should this be excluded from "
                "file-based validation, documented as an access requirement, or "
                "treated as missing supplementary material?"
            )
            default_action = "needs_second_review"

        else:
            question = (
                "This grounding result needs curator review."
            )
            default_action = "needs_second_review"

        targets.append(
            {
                "target_id": f"review_{g.get('logical_file_id')}",
                "logical_file_id": g.get("logical_file_id"),
                "logical_name": g.get("logical_name"),
                "grounding_status": status,
                "question": question,
                "default_action": default_action,
            }
        )

    return targets


def generate_global_warnings(
    grounding_inputs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    warnings = []

    physical_inventory = grounding_inputs.get("physical_inventory", {})
    artifact_sources_overview = grounding_inputs.get("artifact_sources_overview", {})

    if not physical_inventory.get("effective_artifact_root_exists", False):
        warnings.append(
            {
                "warning_type": "missing_effective_artifact_root",
                "severity": "blocking",
                "message": "The effective artifact root does not exist.",
            }
        )

    if physical_inventory.get("num_files", 0) == 0:
        warnings.append(
            {
                "warning_type": "empty_effective_artifact_root",
                "severity": "blocking",
                "message": "The effective artifact root contains no files.",
            }
        )

    existing_sources = [
        name for name, info in artifact_sources_overview.items()
        if info.get("exists") and info.get("num_files", 0) > 0
    ]

    if len(existing_sources) > 1:
        warnings.append(
            {
                "warning_type": "multiple_artifact_sources_available",
                "severity": "low",
                "message": (
                    "Multiple artifact sources are available. Grounding uses the "
                    "effective artifact root only, but other sources may contain "
                    "additional or duplicate files."
                ),
                "sources": existing_sources,
            }
        )

    return warnings


class RefinedArtifactGrounder:
    """
    Rule-based physical grounding for selected-50.

    Input:
      logical claims from dataset_structure.json
      physical inventory from effective_artifact_root

    Output:
      refined_artifact_grounding.json

    This class does not modify dataset_structure.json.
    """

    def ground(
        self,
        grounding_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        article_id = grounding_inputs.get("article_id", "unknown")

        logical_claims = grounding_inputs.get("logical_claims", {})
        physical_inventory = grounding_inputs.get("physical_inventory", {})

        logical_files = logical_claims.get("logical_files") or []
        physical_files = physical_file_candidates(physical_inventory)

        file_groundings = [
            ground_one_logical_file(
                logical_file=logical_file,
                physical_files=physical_files,
            )
            for logical_file in logical_files
        ]

        summary = summarize_file_groundings(file_groundings)
        human_review_targets = generate_human_review_targets(file_groundings)
        global_warnings = generate_global_warnings(grounding_inputs)

        return {
            "schema_version": "physical_grounding_v1",
            "article_id": article_id,
            "generated_at": datetime.now().isoformat(),

            "input_layers": {
                "logical_schema_path": logical_claims.get("schema_path"),
                "effective_artifact_root": physical_inventory.get(
                    "effective_artifact_root"
                ),
                "effective_artifact_source": physical_inventory.get(
                    "effective_artifact_source"
                ),
            },

            "logical_summary": logical_claims.get("summary", {}),
            "physical_summary": {
                "effective_artifact_root_exists": physical_inventory.get(
                    "effective_artifact_root_exists"
                ),
                "num_physical_files": physical_inventory.get("num_files", 0),
                "num_tabular_candidates": physical_inventory.get(
                    "num_tabular_candidates",
                    0,
                ),
            },

            "file_groundings": file_groundings,
            "summary": summary,
            "global_warnings": global_warnings,
            "human_review_targets": human_review_targets,
        }
