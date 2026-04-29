from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
STRUCTURED_DOCS_DIR = DATA_DIR / "structured_docs"
RESULTS_DIR = PROJECT_ROOT / "results"
RUNS_DIR = RESULTS_DIR / "runs"

# Prefer private local config. Do not commit src/utils/local_config.py.
try:
    from .local_config import LLM_CONFIG  # type: ignore
except ImportError:
    LLM_CONFIG = {
        "model_name": os.getenv("DOC2VALIDATE_LLM_MODEL", "qwen-30b"),
        "api_base_url": os.getenv("DOC2VALIDATE_LLM_BASE_URL", "http://localhost:8000/v1"),
        "api_key": os.getenv("DOC2VALIDATE_LLM_API_KEY", "EMPTY"),
        "temperature": float(os.getenv("DOC2VALIDATE_LLM_TEMPERATURE", "0.3")),
        "max_tokens": int(os.getenv("DOC2VALIDATE_LLM_MAX_TOKENS", "4000")),
        "context_window": int(os.getenv("DOC2VALIDATE_LLM_CONTEXT_WINDOW", "32000")),
        "timeout": int(os.getenv("DOC2VALIDATE_LLM_TIMEOUT", "60")),
        "max_retries": int(os.getenv("DOC2VALIDATE_LLM_MAX_RETRIES", "3")),
    }


def get_run_dirs(run_name: str) -> Dict[str, Path]:
    run_dir = RUNS_DIR / run_name
    return {
        "run_dir": run_dir,
        "logs_dir": run_dir / "logs",
        "manifests_dir": run_dir / "manifests",
    }


def ensure_run_dirs(run_name: str) -> Dict[str, Path]:
    dirs = get_run_dirs(run_name)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def get_all_article_ids(structured_docs_dir: Path = STRUCTURED_DOCS_DIR) -> List[str]:
    if not structured_docs_dir.exists():
        return []
    article_ids: List[str] = []
    for item in structured_docs_dir.iterdir():
        if item.is_dir() and (item / "structured_data.json").exists():
            article_ids.append(item.name)
    return sorted(article_ids)


def get_article_structure(article_id: str) -> Dict[str, Any]:
    article_dir = STRUCTURED_DOCS_DIR / article_id
    structured_data_path = article_dir / "structured_data.json"
    if not structured_data_path.exists():
        raise FileNotFoundError(f"structured_data.json not found: {structured_data_path}")
    return {
        "article_id": article_id,
        "article_dir": article_dir,
        "json_data_dir": article_dir,
        "structured_data_path": structured_data_path,
        "dataset_result_path": article_dir / "dataset.json",
        "code_repository_result_path": article_dir / "code_repository.json",
        "validation_dir": article_dir / "validation",
        "scraped_repository_path": article_dir / "scraped_repository.json",
    }
