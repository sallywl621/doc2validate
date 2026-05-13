from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.execution.runtime_failure_taxonomy import (
    EXEC_NO_GENERATED_CODE,
    EXEC_NO_RUN_OUTPUT,
    EXEC_NO_RUN_SCRIPT,
    EXEC_REQUIREMENTS_INSTALL_FAILED,
    EXEC_RUN_OUTPUT_PARSE_FAILED,
    EXEC_SUCCESS,
    RuntimeFailure,
    classify_process_failure,
    classify_run_output,
)


class WorkflowExecutor:
    """Execute one generated validation scaffold and classify runtime failures."""

    def __init__(self, *, python_executable: str | None = None, timeout_seconds: int = 300, install_requirements: bool = False):
        self.python_executable = python_executable or sys.executable
        self.timeout_seconds = timeout_seconds
        self.install_requirements = install_requirements

    def execute(self, *, article_id: str, generated_code_dir: Path, execution_output_dir: Path) -> Dict[str, Any]:
        execution_output_dir.mkdir(parents=True, exist_ok=True)
        result: Dict[str, Any] = {
            "article_id": article_id,
            "executor_version": "execution_v0.1.0",
            "generated_code_dir": str(generated_code_dir),
            "execution_output_dir": str(execution_output_dir),
            "started_at": datetime.utcnow().isoformat() + "Z",
            "finished_at": None,
            "process": None,
            "run_output": None,
            "execution_status": "unknown",
            "runtime_failure": None,
        }

        if not generated_code_dir.exists():
            return self._finish_with_failure(result, RuntimeFailure(EXEC_NO_GENERATED_CODE, "generated code directory does not exist", "executor"))

        run_py = generated_code_dir / "run.py"
        if not run_py.exists():
            return self._finish_with_failure(result, RuntimeFailure(EXEC_NO_RUN_SCRIPT, "run.py does not exist in generated code directory", "executor"))

        if self.install_requirements:
            req_path = generated_code_dir / "requirements.txt"
            if req_path.exists():
                install = subprocess.run(
                    [self.python_executable, "-m", "pip", "install", "-r", str(req_path)],
                    cwd=str(generated_code_dir), capture_output=True, text=True, timeout=self.timeout_seconds,
                )
                if install.returncode != 0:
                    result["process"] = {"phase": "install_requirements", "returncode": install.returncode, "stdout": install.stdout, "stderr": install.stderr}
                    return self._finish_with_failure(result, RuntimeFailure(EXEC_REQUIREMENTS_INSTALL_FAILED, "pip install -r requirements.txt failed", "subprocess"))

        stdout = ""
        stderr = ""
        returncode = None
        timed_out = False
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{generated_code_dir}:{env.get('PYTHONPATH', '')}"

        try:
            proc = subprocess.run(
                [self.python_executable, "run.py"], cwd=str(generated_code_dir), capture_output=True, text=True,
                timeout=self.timeout_seconds, env=env,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

        process_failure = classify_process_failure(returncode=returncode, stdout=stdout, stderr=stderr, timed_out=timed_out)
        result["process"] = {"returncode": returncode, "timed_out": timed_out, "stdout": stdout, "stderr": stderr}
        self._write_text(execution_output_dir / "stdout.txt", stdout)
        self._write_text(execution_output_dir / "stderr.txt", stderr)

        if process_failure.category != EXEC_SUCCESS:
            return self._finish_with_failure(result, process_failure)

        run_output_path = generated_code_dir / "run_output.json"
        if not run_output_path.exists():
            return self._finish_with_failure(result, RuntimeFailure(EXEC_NO_RUN_OUTPUT, "run.py completed but did not produce run_output.json", "executor"))

        try:
            run_output = json.loads(run_output_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return self._finish_with_failure(result, RuntimeFailure(EXEC_RUN_OUTPUT_PARSE_FAILED, f"failed to parse run_output.json: {type(exc).__name__}: {exc}", "executor"))

        result["run_output"] = run_output
        shutil.copy2(run_output_path, execution_output_dir / "run_output.json")
        output_failure = classify_run_output(run_output)
        result["execution_status"] = "success" if output_failure.category == EXEC_SUCCESS else "runtime_failed"
        result["runtime_failure"] = asdict(output_failure)
        result["finished_at"] = datetime.utcnow().isoformat() + "Z"
        self._write_json(execution_output_dir / "execution_result.json", result)
        return result

    def _finish_with_failure(self, result: Dict[str, Any], failure: RuntimeFailure) -> Dict[str, Any]:
        result["execution_status"] = "success" if failure.category == EXEC_SUCCESS else "runtime_failed"
        result["runtime_failure"] = asdict(failure)
        result["finished_at"] = datetime.utcnow().isoformat() + "Z"
        out_dir = Path(result["execution_output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(out_dir / "execution_result.json", result)
        return result

    @staticmethod
    def _write_json(path: Path, obj: Dict[str, Any]) -> None:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _write_text(path: Path, text: str) -> None:
        path.write_text(text or "", encoding="utf-8")
