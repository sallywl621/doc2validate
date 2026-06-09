from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import pandas as pd


DATA_FILE_EXTENSIONS = {
    ".csv", ".tsv", ".json", ".jsonl",
    ".xlsx", ".xls",
    ".parquet", ".feather",
    ".h5", ".hdf5",
    ".npy", ".npz",
    ".txt",
    ".zip", ".tar.gz", ".tgz", ".gz",
}


def classify_url(url: str) -> str:
    lowered = url.lower()
    domain = urlparse(url).netloc.lower()

    if "github.com" in lowered:
        return "github"

    if "zenodo.org" in lowered:
        return "zenodo"

    if lowered.endswith(".tar.gz"):
        return "direct_file"

    if any(lowered.endswith(ext) for ext in DATA_FILE_EXTENSIONS):
        return "direct_file"

    if "figshare" in domain:
        return "figshare_landing_page"

    if "dataverse" in domain:
        return "dataverse_landing_page"

    if "dryad" in domain:
        return "dryad_landing_page"

    if "osf.io" in domain:
        return "osf_landing_page"

    if "physionet" in domain:
        return "physionet_landing_page"

    return "other_landing_or_unknown"


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_accessible_dataset_urls(validation_dir: Path) -> List[str]:
    path = validation_dir / "dataset_url_validation.json"

    if not path.exists():
        return []

    try:
        data = load_json(path)
    except Exception:
        return []

    urls: List[str] = []

    for item in data.get("results", []):
        if item.get("accessible") is True:
            url = item.get("redirected_url") or item.get("url")
            if url:
                urls.append(url)

    return sorted(set(urls))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze dataset download candidates from URL validation results. "
            "This is a preflight analysis for artifact downloading."
        )
    )
    parser.add_argument("--run-name", required=True)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("/mydata/doc2validate"),
    )

    args = parser.parse_args()

    root = args.project_root
    run_dir = root / "results" / "runs" / args.run_name
    out_dir = run_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    structured_root = root / "data" / "structured_docs"

    rows: List[Dict[str, Any]] = []

    for article_dir in sorted(structured_root.iterdir()):
        if not article_dir.is_dir():
            continue

        article_id = article_dir.name
        validation_dir = article_dir / "validation"

        urls = collect_accessible_dataset_urls(validation_dir)
        url_types = [classify_url(u) for u in urls]

        supported_types = {"github", "zenodo", "direct_file"}
        has_supported = any(t in supported_types for t in url_types)

        rows.append(
            {
                "article_id": article_id,
                "accessible_dataset_url_count": len(urls),
                "has_supported_download_handler": has_supported,
                "supported_download_url_count": sum(
                    1 for t in url_types if t in supported_types
                ),
                "unsupported_download_url_count": sum(
                    1 for t in url_types if t not in supported_types
                ),
                "github_url_count": url_types.count("github"),
                "zenodo_url_count": url_types.count("zenodo"),
                "direct_file_url_count": url_types.count("direct_file"),
                "landing_or_unknown_url_count": sum(
                    1 for t in url_types if t not in supported_types
                ),
                "download_handler_types": json.dumps(
                    sorted(set(url_types)),
                    ensure_ascii=False,
                ),
                "candidate_urls": json.dumps(urls, ensure_ascii=False),
            }
        )

    df = pd.DataFrame(rows)

    preflight_csv = out_dir / "download_candidate_preflight.csv"
    downloadable_csv = out_dir / "downloadable_candidates.csv"
    downloadable_ids = out_dir / "downloadable_article_ids.txt"

    df.to_csv(preflight_csv, index=False)

    downloadable = df[df["has_supported_download_handler"]].copy()
    downloadable.to_csv(downloadable_csv, index=False)

    ids = sorted(downloadable["article_id"].dropna().unique())
    downloadable_ids.write_text(
        "\n".join(ids) + ("\n" if ids else ""),
        encoding="utf-8",
    )

    total_counter: Counter[str] = Counter()
    for raw in df["download_handler_types"]:
        for t in json.loads(raw):
            total_counter[t] += 1

    url_type_counter: Counter[str] = Counter()
    for raw in df["candidate_urls"]:
        for u in json.loads(raw):
            url_type_counter[classify_url(u)] += 1

    print(f"Wrote: {preflight_csv}")
    print(f"Wrote: {downloadable_csv}")
    print(f"Wrote: {downloadable_ids}")
    print()
    print(f"Articles: {len(df)}")
    print(
        "Articles with accessible dataset URLs:",
        int((df["accessible_dataset_url_count"] > 0).sum()),
    )
    print(
        "Articles with downloader-supported URLs:",
        int(df["has_supported_download_handler"].sum()),
    )
    print()
    print("URL type totals:")
    for k, v in url_type_counter.most_common():
        print(f"  {k}: {v}")

    print()
    print("Article-level handler counts:")
    print("  github articles:", int((df["github_url_count"] > 0).sum()))
    print("  zenodo articles:", int((df["zenodo_url_count"] > 0).sum()))
    print("  direct_file articles:", int((df["direct_file_url_count"] > 0).sum()))
    print(
        "  landing/unknown only articles:",
        int(
            (
                (df["accessible_dataset_url_count"] > 0)
                & (~df["has_supported_download_handler"])
            ).sum()
        ),
    )

    print()
    print(
        "Rough downloadable upper bound:",
        int(df["has_supported_download_handler"].sum()),
    )
    print(
        "Likely no-download due to unsupported landing pages:",
        int(
            (
                (df["accessible_dataset_url_count"] > 0)
                & (~df["has_supported_download_handler"])
            ).sum()
        ),
    )
    print(
        "No accessible dataset URLs:",
        int((df["accessible_dataset_url_count"] == 0).sum()),
    )


if __name__ == "__main__":
    main()
