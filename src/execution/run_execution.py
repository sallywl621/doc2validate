from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from src.execution.executor import WorkflowExecutor
from src.utils.config import RESULTS_DIR, ensure_run_dirs, get_run_article_ids
from src.utils.io import write_manifest
from src.utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--max-articles", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--python-executable", type=str)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--install-requirements", action="store_true")
    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)
    setup_logging(args.log_path or dirs["logs_dir"] / "execution.log")

    article_ids = get_run_article_ids(args.run_name)
    if args.max_articles is not None:
        article_ids = article_ids[: args.max_articles]

    executor = WorkflowExecutor(
        python_executable=args.python_executable,
        timeout_seconds=args.timeout_seconds,
        install_requirements=args.install_requirements,
    )

    rows = []
    for article_id in article_ids:
        started = datetime.utcnow().isoformat() + "Z"
        generated_code_dir = RESULTS_DIR / "runs" / args.run_name / "generated_code" / article_id
        execution_output_dir = RESULTS_DIR / "runs" / args.run_name / "execution" / article_id
        execution_result_path = execution_output_dir / "execution_result.json"

        status = "unknown"
        failure_category = ""
        failure_detail = ""
        returncode = ""
        timed_out = ""

        if execution_result_path.exists() and not args.overwrite:
            status = "skipped_existing"
        else:
            logging.info("Executing generated workflow: %s", article_id)
            result = executor.execute(article_id=article_id, generated_code_dir=generated_code_dir, execution_output_dir=execution_output_dir)
            status = result.get("execution_status", "unknown")
            failure = result.get("runtime_failure") or {}
            failure_category = failure.get("category", "")
            failure_detail = failure.get("detail", "")
            process = result.get("process") or {}
            returncode = process.get("returncode", "")
            timed_out = process.get("timed_out", "")

        rows.append({
            "article_id": article_id,
            "status": status,
            "runtime_failure_category": failure_category,
            "runtime_failure_detail": failure_detail,
            "returncode": returncode,
            "timed_out": timed_out,
            "generated_code_dir": str(generated_code_dir),
            "execution_output_dir": str(execution_output_dir),
            "execution_result_path": str(execution_result_path),
            "started_at": started,
            "finished_at": datetime.utcnow().isoformat() + "Z",
        })
        logging.info("%s: %s %s", article_id, status, failure_category)

    out_manifest = args.manifest or dirs["manifests_dir"] / "execution_manifest.csv"
    write_manifest(rows, out_manifest)
    logging.info("Manifest written: %s", out_manifest)


if __name__ == "__main__":
    main()
