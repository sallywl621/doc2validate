from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import fnmatch
import re


# =========================================================
# =============== V1 CONSTANTS (INLINE COPY) ===============
# =========================================================

RESOLVED_THRESHOLD = 0.80
CANDIDATE_THRESHOLD = 0.45
FORMAT_ONLY_SCORE = 0.20


# =========================================================
# =============== V1 UTILS (INLINE COPY) ==================
# =========================================================

def is_unknown(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "unknown", "none", "null", "n/a", "na"}


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
    return {t for t in text.split("_") if t and len(t) >= 2}


def get_expected_suffix(expected_format: Any) -> str:
    fmt = str(expected_format or "").strip().lower()
    if fmt in {"csv", "tsv", "xlsx", "xls", "parquet"}:
        return f".{fmt}"
    return ""


# =========================================================
# =============== V1 CORE MATCHING (INLINE COPY) ==========
# =========================================================

def score_single_match(logical_file: Dict[str, Any], physical_file: Dict[str, Any]) -> Tuple[float, str]:

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

    if pattern_str and rel_path == pattern_str:
        return 1.00, "exact_relative_path"

    if pattern_name and name == pattern_name:
        return 0.95, "exact_basename"

    if pattern_str and any(ch in pattern_str for ch in ["*", "?", "["]):
        if fnmatch.fnmatch(rel_path, pattern_str) or fnmatch.fnmatch(name, pattern_str):
            return 0.90, "glob_pattern"

    if pattern_stem and normalize_text(pattern_stem) == normalize_text(stem):
        return 0.85, "stem_match"

    if pattern_name and normalize_text(pattern_name) == normalize_text(name):
        return 0.80, "normalized_basename"

    norm_pattern_stem = normalize_text(pattern_stem)
    norm_stem = normalize_text(stem)

    if norm_pattern_stem and norm_stem:
        if norm_pattern_stem in norm_stem or norm_stem in norm_pattern_stem:
            return 0.65, "stem_contains"

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

    if expected_suffix and suffix == expected_suffix:
        return FORMAT_ONLY_SCORE, "format_only"

    return 0.0, "no_match"


# =========================================================
# =============== V1 PIPELINE (INLINE COPY) ===============
# =========================================================

def score_logical_file_against_inventory(logical_file, physical_files):
    scored = []

    for pf in physical_files:
        score, match_type = score_single_match(logical_file, pf)

        if score <= 0:
            continue

        scored.append({
            "relative_path": pf.get("relative_path"),
            "name": pf.get("name"),
            "stem": pf.get("stem"),
            "suffix": pf.get("suffix"),
            "match_score": round(score, 4),
            "match_type": match_type,
            "columns": pf.get("columns", [])   # 👈 IMPORTANT FOR V2 COLUMN LOGIC
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored


def determine_best_match(candidates):
    if not candidates:
        return None, "missing"

    top = candidates[0]
    score = top["match_score"]

    if score >= RESOLVED_THRESHOLD:
        return top, "resolved"
    if score >= CANDIDATE_THRESHOLD:
        return top, "ambiguous"
    return top, "weak_match"


# =========================================================
# =============== COLUMN-WISE (V2 NEW ONLY) ===============
# =========================================================

def column_match_score(lc, pc):

    name_score = 1.0 if lc.get("name") == pc.get("name") else 0.3
    type_score = 1.0 if lc.get("type") == pc.get("type") else 0.5

    return 0.6 * name_score + 0.4 * type_score


def column_grounding_v2(logical_file, physical_file):

    logical_cols = logical_file.get("columns", [])
    physical_cols = physical_file.get("columns", [])

    results = []

    for lc in logical_cols:

        best = None
        best_score = 0.0

        for pc in physical_cols:
            score = column_match_score(lc, pc)

            if score > best_score:
                best_score = score
                best = pc

        results.append({
            "logical_column": lc,
            "matched_column": best,
            "score": best_score
        })

    return results


# =========================================================
# =============== V2 MAIN CLASS (NO IMPORT V1) ============
# =========================================================

class RefinedArtifactGrounderV2:

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def ground(self, grounding_inputs):

        logical_files = grounding_inputs["logical_claims"]["logical_files"]
        physical_files = grounding_inputs["physical_inventory"]["files"]

        v2_results = []

        for lf in logical_files:

            candidates = score_logical_file_against_inventory(lf, physical_files)

            best, status = determine_best_match(candidates)

            result = {
                "logical_file": lf,
                "status": status,
                "best_match": best,
                "candidates": candidates,
            }

            # =========================
            # COLUMN-WISE ONLY IF RESOLVED
            # =========================
            if status == "resolved" and best:
                result["column_grounding"] = column_grounding_v2(lf, best)

            v2_results.append(result)

        # =========================
        # OPTIONAL LLM AUDIT ONLY
        # =========================
        llm_audit = None
        if self.llm:
            llm_audit = self.llm.ask({
                "task": "audit_only",
                "input": v2_results
            })

        return {
            "file_grounding_v2": v2_results,
            "llm_audit": llm_audit
        }
