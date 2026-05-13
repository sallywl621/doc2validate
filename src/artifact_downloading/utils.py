from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse


DATA_FILE_EXTENSIONS = {
    ".csv", ".tsv", ".json", ".jsonl", ".xlsx", ".xls",
    ".parquet", ".feather", ".h5", ".hdf5",
    ".npy", ".npz", ".txt",
    ".zip", ".tar.gz", ".tgz", ".gz",
}

CODE_FILE_EXTENSIONS = {
    ".py", ".ipynb", ".R", ".r", ".java", ".cpp",
    ".c", ".js", ".ts", ".sh",
}

SKIP_DIR_KEYWORDS = {
    ".git", "__pycache__", "src", "code", "scripts",
    "notebooks", "docs", "doc", "test", "tests", "examples",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def is_github_url(url: str) -> bool:
    return "github.com" in url.lower()


def is_zenodo_url(url: str) -> bool:
    return "zenodo.org" in url.lower()


def is_direct_artifact_url(url: str) -> bool:
    lowered = url.lower()
    return any(lowered.endswith(ext) for ext in DATA_FILE_EXTENSIONS)


def is_compressed_archive(path_or_url: str) -> bool:
    lowered = path_or_url.lower()
    return lowered.endswith((".zip", ".tar.gz", ".tgz", ".gz"))


def is_data_file(path: Path) -> bool:
    lowered = path.name.lower()
    if lowered.endswith(".tar.gz"):
        return True
    return path.suffix.lower() in DATA_FILE_EXTENSIONS


def is_code_file(path: Path) -> bool:
    return path.suffix in CODE_FILE_EXTENSIONS


def should_skip_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}

    if parts & SKIP_DIR_KEYWORDS:
        return True

    if is_code_file(path):
        return True

    return False


def safe_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.netloc}_{parsed.path}".strip("_/")
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)
    return raw[:180] or "resource"


def parse_github_url(url: str) -> dict:
    cleaned = url.rstrip("/")
    parsed = urlparse(cleaned)
    parts = [p for p in parsed.path.split("/") if p]

    if "github.com" not in parsed.netloc.lower() or len(parts) < 2:
        return {
            "valid": False,
            "original_url": url,
            "repo_url": url,
            "owner": None,
            "repo": None,
            "kind": None,
            "branch": None,
            "subpath": None,
        }

    owner = parts[0]
    repo = parts[1].replace(".git", "")
    repo_url = f"https://github.com/{owner}/{repo}"

    kind = None
    branch = None
    subpath = None

    if len(parts) >= 5 and parts[2] in {"tree", "blob"}:
        kind = parts[2]
        branch = parts[3]
        subpath = "/".join(parts[4:])

    return {
        "valid": True,
        "original_url": url,
        "repo_url": repo_url,
        "owner": owner,
        "repo": repo,
        "kind": kind,
        "branch": branch,
        "subpath": subpath,
    }


def github_archive_urls(owner: str, repo: str, branch: str | None) -> list[tuple[str, str]]:
    if branch:
        return [
            (
                branch,
                f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip",
            )
        ]

    return [
        (
            "main",
            f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip",
        ),
        (
            "master",
            f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip",
        ),
    ]
