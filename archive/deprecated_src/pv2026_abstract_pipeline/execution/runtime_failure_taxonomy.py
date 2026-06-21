from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

EXEC_SUCCESS = "EXEC_SUCCESS"
EXEC_NO_GENERATED_CODE = "EXEC_NO_GENERATED_CODE"
EXEC_NO_RUN_SCRIPT = "EXEC_NO_RUN_SCRIPT"
EXEC_REQUIREMENTS_INSTALL_FAILED = "EXEC_REQUIREMENTS_INSTALL_FAILED"
EXEC_FILE_NOT_FOUND = "EXEC_FILE_NOT_FOUND"
EXEC_LOAD_FAILED = "EXEC_LOAD_FAILED"
EXEC_MISSING_COLUMNS = "EXEC_MISSING_COLUMNS"
EXEC_PARSER_ERROR = "EXEC_PARSER_ERROR"
EXEC_UNSUPPORTED_FORMAT = "EXEC_UNSUPPORTED_FORMAT"
EXEC_PERMISSION_DENIED = "EXEC_PERMISSION_DENIED"
EXEC_MEMORY_ERROR = "EXEC_MEMORY_ERROR"
EXEC_TIMEOUT = "EXEC_TIMEOUT"
EXEC_RUNTIME_EXCEPTION = "EXEC_RUNTIME_EXCEPTION"
EXEC_NO_RUN_OUTPUT = "EXEC_NO_RUN_OUTPUT"
EXEC_RUN_OUTPUT_PARSE_FAILED = "EXEC_RUN_OUTPUT_PARSE_FAILED"
EXEC_NO_RUNS_IN_OUTPUT = "EXEC_NO_RUNS_IN_OUTPUT"
EXEC_ALL_LOADS_FAILED = "EXEC_ALL_LOADS_FAILED"
EXEC_VALIDATION_FAILED = "EXEC_VALIDATION_FAILED"
EXEC_UNKNOWN_FAILURE = "EXEC_UNKNOWN_FAILURE"


@dataclass
class RuntimeFailure:
    category: str
    detail: str
    source: Optional[str] = None


def classify_process_failure(*, returncode: int | None, stdout: str, stderr: str, timed_out: bool) -> RuntimeFailure:
    text = f"{stdout}\n{stderr}".lower()
    if timed_out:
        return RuntimeFailure(EXEC_TIMEOUT, "generated workflow exceeded execution timeout", "subprocess")
    if returncode == 0:
        return RuntimeFailure(EXEC_SUCCESS, "process completed successfully", "subprocess")
    if "filenotfounderror" in text or "no such file or directory" in text:
        return RuntimeFailure(EXEC_FILE_NOT_FOUND, "data file or required local path was not found", "subprocess")
    if "permissionerror" in text or "permission denied" in text:
        return RuntimeFailure(EXEC_PERMISSION_DENIED, "permission denied while accessing a file or directory", "subprocess")
    if "parsererror" in text or "tokenizing data" in text:
        return RuntimeFailure(EXEC_PARSER_ERROR, "parser failed to read the target data file", "subprocess")
    if "memoryerror" in text or "out of memory" in text:
        return RuntimeFailure(EXEC_MEMORY_ERROR, "execution failed due to memory exhaustion", "subprocess")
    if "unsupported" in text and "format" in text:
        return RuntimeFailure(EXEC_UNSUPPORTED_FORMAT, "generated loader encountered unsupported format", "subprocess")
    if "importerror" in text or "modulenotfounderror" in text:
        return RuntimeFailure(EXEC_RUNTIME_EXCEPTION, "runtime dependency import failed", "subprocess")
    return RuntimeFailure(EXEC_RUNTIME_EXCEPTION, f"generated workflow exited with return code {returncode}", "subprocess")


def classify_run_output(run_output: dict) -> RuntimeFailure:
    runs = run_output.get("runs", [])
    if not isinstance(runs, list) or len(runs) == 0:
        return RuntimeFailure(EXEC_NO_RUNS_IN_OUTPUT, "run_output.json contains no runs", "run_output")

    any_load_ok = False
    any_validation_ok = False
    missing_columns = False
    load_errors = []

    for item in runs:
        load_result = item.get("load_result", {}) or {}
        validation = item.get("validation", {}) or {}
        if load_result.get("ok") is True:
            any_load_ok = True
        if validation.get("ok") is True:
            any_validation_ok = True
        for v in validation.get("items", []) or []:
            if isinstance(v, dict) and v.get("name") == "expected_columns" and v.get("ok") is False:
                missing_columns = True
        if load_result.get("ok") is False:
            err = load_result.get("error") or load_result.get("detail")
            if err:
                load_errors.append(str(err))

    if any_load_ok:
        if missing_columns and not any_validation_ok:
            return RuntimeFailure(EXEC_MISSING_COLUMNS, "at least one file loaded, but expected columns were missing", "run_output")
        return RuntimeFailure(EXEC_SUCCESS, "at least one target file loaded successfully", "run_output")

    joined_errors = "\n".join(load_errors).lower()
    if "not found" in joined_errors or "no such file" in joined_errors:
        return RuntimeFailure(EXEC_FILE_NOT_FOUND, "all loads failed because target files were not found", "run_output")
    if "parser" in joined_errors or "tokenizing" in joined_errors:
        return RuntimeFailure(EXEC_PARSER_ERROR, "all loads failed due to parser errors", "run_output")
    if "unsupported" in joined_errors and "format" in joined_errors:
        return RuntimeFailure(EXEC_UNSUPPORTED_FORMAT, "all loads failed due to unsupported file format", "run_output")
    return RuntimeFailure(EXEC_ALL_LOADS_FAILED, "generated workflow ran, but all target file loads failed", "run_output")
