import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.selected50.benchmark_loader import (
    load_all_selected50_cases,
    load_logical_claim,
)
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


# ============================================================
# Utils
# ============================================================

def tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_]+", str(text).lower()) if t]


def exec_level(exec_flag: bool, requires_human: bool):
    if exec_flag and not requires_human:
        return "executable"
    if exec_flag:
        return "semi_executable"
    return "human_only"


def classify(text: str, patterns: List[Tuple[str, List[str]]], fallback: str):
    text_l = str(text).lower()
    for cat, terms in patterns:
        for t in terms:
            if t in text_l:
                return cat, [t]
    return fallback, []


# ============================================================
# File mapping
# ============================================================

def map_to_file(text: str, files: List[Dict]):
    text_l = str(text).lower()

    best = None
    best_score = 0

    for f in files:
        score = 0

        name = f.get("logical_name", "").lower()
        pattern = f.get("file_pattern", "").lower()
        path = f.get("path", "").lower()

        if name and name in text_l:
            score += 5
        if pattern and pattern in text_l:
            score += 4
        if path and path in text_l:
            score += 4

        overlap = len(set(tokenize(text)) & set(f.get("tokens", [])))
        score += overlap

        if score > best_score:
            best_score = score
            best = f

    if not best or best_score < 2:
        return {
            "target_scope": "article",
            "mapped_logical_file_id": "",
            "mapped_logical_name": "",
            "mapping_score": 0.0,
        }

    return {
        "target_scope": "logical_file",
        "mapped_logical_file_id": best.get("logical_file_id"),
        "mapped_logical_name": best.get("logical_name"),
        "mapping_score": best_score,
    }


def normalize_files(files):
    out = []

    for i, f in enumerate(files or []):
        structure = f.get("structure", {}) or {}
        cols = list((structure.get("columns", {}) or {}).keys())

        out.append({
            "logical_file_id": f.get("logical_file_id", f"lf_{i}"),
            "logical_name": f.get("logical_name", ""),
            "file_pattern": f.get("file_pattern", ""),
            "path": f.get("path", ""),
            "tokens": tokenize(" ".join(cols + [f.get("logical_name", "")])),
        })

    return out


# ============================================================
# Core
# ============================================================

def analyze_case(case):

    # ========================================================
    # CRITICAL FIX: single canonical loader ONLY
    # ========================================================
    structure = load_logical_claim(case)

    if not structure:
        return {
            "article_id": case.article_id,
            "status": "error",
            "reason": "missing_logical_claim"
        }

    # ========================================================
    # direct fields (NO raw, NO safe_get_structure)
    # ========================================================
    validation_targets = structure.get("validation_targets", []) or []
    execution_notes = structure.get("execution_relevant_notes", []) or []
    files = normalize_files(structure.get("files", []) or [])

    affordances = []

    # ========================================================
    # validation affordances
    # ========================================================
    for t in validation_targets:

        cat, terms = classify(
            t,
            [
                ("schema_check", ["column", "schema", "field"]),
                ("range_check", ["range", "min", "max", "unit"]),
                ("missingness_check", ["missing", "null"]),
                ("linkage_check", ["id", "key", "mapping"]),
            ],
            "unknown",
        )

        m = map_to_file(t, files)

        exec_flag = cat in {
            "schema_check",
            "range_check",
            "missingness_check",
            "linkage_check",
        }

        affordances.append({
            "source": "validation_targets",
            "raw_text": t,
            "category": cat,
            "matched_terms": terms,
            "potentially_executable": exec_flag,
            "requires_human_review": not exec_flag,
            "affordance_exec_level": exec_level(exec_flag, False),
            **m,
        })

    # ========================================================
    # execution affordances
    # ========================================================
    for t in execution_notes:

        cat, terms = classify(
            t,
            [
                ("dependency", ["python", "docker", "library"]),
                ("workflow", ["run", "execute", "notebook"]),
                ("archive", ["zip", "tar", "gzip"]),
                ("api", ["api", "endpoint", "url"]),
            ],
            "unknown",
        )

        m = map_to_file(t, files)

        exec_flag = cat in {"dependency", "workflow", "archive"}

        affordances.append({
            "source": "execution_relevant_notes",
            "raw_text": t,
            "category": cat,
            "matched_terms": terms,
            "potentially_executable": exec_flag,
            "requires_human_review": True,
            "affordance_exec_level": exec_level(exec_flag, True),
            **m,
        })

    # ========================================================
    # summary (PPT-ready)
    # ========================================================
    summary = {
        "num_validation_targets": len(validation_targets),
        "num_execution_notes": len(execution_notes),
        "num_affordances": len(affordances),

        "num_executable": sum(a["affordance_exec_level"] == "executable" for a in affordances),
        "num_semi_executable": sum(a["affordance_exec_level"] == "semi_executable" for a in affordances),
        "num_human_only": sum(a["affordance_exec_level"] == "human_only" for a in affordances),

        "num_mapped": sum(a["target_scope"] == "logical_file" for a in affordances),
    }

    return {
        "article_id": case.article_id,
        "status": "success",
        "summary": summary,
        "affordances": affordances,
    }


# ============================================================
# CLI
# ============================================================

def main():

    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-root", type=Path, required=True)
    ap.add_argument("--article-id", type=str)
    args = ap.parse_args()

    setup_logging(args.benchmark_root / "validation_affordance.log")

    cases = load_all_selected50_cases(
        benchmark_root=args.benchmark_root,
        article_id=args.article_id
    )

    articles = []
    items = []

    for c in cases:

        r = analyze_case(c)

        articles.append({
            "article_id": c.article_id,
            **r.get("summary", {}),
            "status": r["status"],
        })

        for a in r.get("affordances", []):
            items.append({
                "article_id": c.article_id,
                **a
            })

    # ========================================================
    # OUTPUT (stable, no per-article filename bug)
    # ========================================================
    out = args.benchmark_root

    write_manifest(
        articles,
        out / "validation_affordance_article_manifest.csv"
    )

    write_manifest(
        items,
        out / "validation_affordance_item_manifest.csv"
    )

    print("DONE")
    print("articles:", len(articles))
    print("items:", len(items))


if __name__ == "__main__":
    main()
