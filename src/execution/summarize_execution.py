from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

from src.utils.config import RESULTS_DIR


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def summarize_execution_manifest(path: Path) -> Dict[str, Any]:
    rows = load_csv(path)
    n_total = len(rows)
    status_counter = Counter(row.get("status", "unknown") for row in rows)
    failure_counter = Counter(row.get("runtime_failure_category") or "NONE" for row in rows)
    examples = defaultdict(list)
    for row in rows:
        cat = row.get("runtime_failure_category") or "NONE"
        if len(examples[cat]) < 5:
            examples[cat].append(row.get("article_id"))
    n_success = status_counter.get("success", 0)
    return {
        "n_total": n_total,
        "n_success": n_success,
        "execution_success_rate": (n_success / n_total) if n_total else 0.0,
        "status_breakdown": dict(status_counter),
        "runtime_failure_breakdown": dict(failure_counter),
        "runtime_failure_examples": dict(examples),
    }


def merge_generation_execution(*, code_generation_manifest: Path, execution_manifest: Path) -> Dict[str, Any]:
    gen_rows = load_csv(code_generation_manifest)
    exec_rows = load_csv(execution_manifest)
    gen_by_id = {r["article_id"]: r for r in gen_rows if r.get("article_id")}
    exec_by_id = {r["article_id"]: r for r in exec_rows if r.get("article_id")}
    article_ids = sorted(set(gen_by_id) | set(exec_by_id))
    generation_success = 0
    execution_success = 0
    generation_failures = Counter()
    runtime_failures = Counter()
    for aid in article_ids:
        gen = gen_by_id.get(aid, {})
        exe = exec_by_id.get(aid, {})
        if gen.get("status") == "success":
            generation_success += 1
        else:
            generation_failures[gen.get("failure_category") or "GEN_UNKNOWN_OR_NOT_ATTEMPTED"] += 1
        if exe.get("status") == "success":
            execution_success += 1
        else:
            runtime_failures[exe.get("runtime_failure_category") or "EXEC_NOT_ATTEMPTED"] += 1
    n = len(article_ids)
    return {
        "n_total": n,
        "n_generation_success": generation_success,
        "generation_success_rate": generation_success / n if n else 0.0,
        "n_execution_success": execution_success,
        "execution_success_rate": execution_success / n if n else 0.0,
        "generation_failure_breakdown": dict(generation_failures),
        "runtime_failure_breakdown": dict(runtime_failures),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    run_dir = RESULTS_DIR / "runs" / args.run_name
    manifest_dir = run_dir / "manifests"
    execution_manifest = manifest_dir / "execution_manifest.csv"
    code_generation_manifest = manifest_dir / "code_generation_manifest.csv"
    summary = {"run_name": args.run_name, "execution": summarize_execution_manifest(execution_manifest)}
    if code_generation_manifest.exists():
        summary["generation_execution"] = merge_generation_execution(code_generation_manifest=code_generation_manifest, execution_manifest=execution_manifest)
    out_path = args.output or manifest_dir / "execution_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
