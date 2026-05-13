from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
STRUCTURED_DOCS_DIR = DATA_DIR / "structured_docs"
DOWNLOADED_ARTIFACTS_DIR = DATA_DIR / "downloaded_artifacts"
RESULTS_DIR = PROJECT_ROOT / "results"


try:
    from src.utils.local_config import LLM_CONFIG
except ImportError:
    LLM_CONFIG = {
        "model_name": "qwen-30b",
        "api_base_url": "http://localhost:8000/v1",
        "api_key": "EMPTY",
        "temperature": 0.3,
        "context_window": 32000,
        "generation_max_tokens": 4000,
        "safe_prompt_budget": 32000,
        "timeout": 60,
        "max_retries": 3,
    }


def ensure_run_dirs(run_name: str) -> Dict[str, Path]:
    run_dir = RESULTS_DIR / "runs" / run_name
    logs_dir = run_dir / "logs"
    manifests_dir = run_dir / "manifests"

    logs_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    return {
        "run_dir": run_dir,
        "logs_dir": logs_dir,
        "manifests_dir": manifests_dir,
    }


def get_all_article_ids() -> List[str]:
    article_ids = []

    if not STRUCTURED_DOCS_DIR.exists():
        return article_ids

    for item in STRUCTURED_DOCS_DIR.iterdir():
        if not item.is_dir():
            continue

        if (item / "structured_data.json").exists():
            article_ids.append(item.name)

    return sorted(article_ids)

def get_run_article_ids(run_name: str) -> List[str]:
    manifest_path = (
        RESULTS_DIR
        / "runs"
        / run_name
        / "manifests"
        / "preprocess_status.csv"
    )

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Preprocess manifest not found: {manifest_path}"
        )

    import csv

    article_ids = []

    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            article_id = (
                row.get("paper_id")
                or row.get("article_id")
            )

            if article_id:
                article_ids.append(article_id)

    return sorted(set(article_ids))

def get_article_structure(article_id: str) -> Dict[str, Any]:
    article_dir = STRUCTURED_DOCS_DIR / article_id
    artifact_dir = DOWNLOADED_ARTIFACTS_DIR / article_id

    if not article_dir.exists():
        raise FileNotFoundError(f"Article directory does not exist: {article_dir}")
    return {
    "article_id": article_id,
    "article_dir": article_dir,
    "json_data_dir": article_dir,
    "structured_data_path": article_dir / "structured_data.json",

    "dataset_extraction_path": article_dir / "dataset.json",
    "code_repository_extraction_path": article_dir / "code_repository.json",

    # Compatibility keys used by extraction runners
    "dataset_result_path": article_dir / "dataset.json",
    "code_repository_result_path": article_dir / "code_repository.json",

    "validation_dir": article_dir / "validation",
    "scraped_repository_path": article_dir / "scraped_repository.json",
    "downloaded_artifacts_dir": DOWNLOADED_ARTIFACTS_DIR / article_id,
    "artifact_download_manifest_path": (
        DOWNLOADED_ARTIFACTS_DIR / article_id / "ARTIFACT_DOWNLOAD_MANIFEST.json"
    ),
}
