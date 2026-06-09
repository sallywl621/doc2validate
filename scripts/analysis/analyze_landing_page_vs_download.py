from pathlib import Path
import json
import pandas as pd


STRUCT_ROOT = Path("data/structured_docs")
ARTIFACT_ROOT = Path("data/downloaded_artifacts")
OUT_DIR = Path("results/runs/scidata_4293/analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)


rows = []

for article_dir in sorted(STRUCT_ROOT.iterdir()):
    if not article_dir.is_dir():
        continue

    article_id = article_dir.name

    scraped_path = article_dir / "scraped_repository.json"
    artifact_dir = ARTIFACT_ROOT / article_id

    has_scraped_json = scraped_path.exists()
    chunk_count = 0
    page_count = None
    root_urls = []
    crawl_source_urls = []

    if has_scraped_json:
        try:
            data = json.loads(scraped_path.read_text(encoding="utf-8"))
            chunks = data.get("chunks", []) or []
            chunk_count = len(chunks)

            metadata = data.get("metadata", {}) or {}
            page_count = metadata.get("page_count")
            root_urls = metadata.get("root_urls", []) or []

            crawl_source_urls = sorted(
                set(
                    c.get("source_url")
                    for c in chunks
                    if c.get("source_url")
                )
            )

        except Exception as exc:
            chunk_count = -1
            crawl_source_urls = []
            root_urls = []
            page_count = None

    has_landing_page_content = chunk_count > 0

    has_artifact_dir = artifact_dir.exists()
    artifact_file_count = 0
    artifact_manifest_exists = False

    if has_artifact_dir:
        artifact_manifest_exists = (
            artifact_dir / "ARTIFACT_DOWNLOAD_MANIFEST.json"
        ).exists()

        artifact_file_count = sum(
            1 for p in artifact_dir.rglob("*")
            if p.is_file()
        )

    download_success_like = (
        has_artifact_dir
        and artifact_file_count > 0
    )

    rows.append(
        {
            "article_id": article_id,
            "has_scraped_repository_json": has_scraped_json,
            "has_landing_page_content": has_landing_page_content,
            "chunk_count": chunk_count,
            "page_count": page_count,
            "root_urls": json.dumps(root_urls, ensure_ascii=False),
            "crawl_source_urls": json.dumps(crawl_source_urls, ensure_ascii=False),
            "has_artifact_dir": has_artifact_dir,
            "artifact_manifest_exists": artifact_manifest_exists,
            "artifact_file_count": artifact_file_count,
            "download_success_like": download_success_like,
            "landing_accessible_but_no_download": (
                has_landing_page_content
                and not download_success_like
            ),
        }
    )


df = pd.DataFrame(rows)

out_csv = OUT_DIR / "landing_page_vs_download.csv"
df.to_csv(out_csv, index=False)

print("Saved:", out_csv)

print("\n=== COUNTS ===")
print("articles total:", len(df))
print("has scraped_repository.json:", df.has_scraped_repository_json.sum())
print("has landing page content:", df.has_landing_page_content.sum())
print("download success-like:", df.download_success_like.sum())
print(
    "landing accessible but no download:",
    df.landing_accessible_but_no_download.sum(),
)

print("\n=== CROSS TAB ===")
print(
    pd.crosstab(
        df.has_landing_page_content,
        df.download_success_like,
        rownames=["landing_page_content"],
        colnames=["download_success_like"],
    )
)

print("\n=== LANDING ACCESSIBLE BUT NO DOWNLOAD ===")
cols = [
    "article_id",
    "chunk_count",
    "page_count",
    "artifact_file_count",
    "root_urls",
]
print(
    df[df.landing_accessible_but_no_download][cols]
    .to_string(index=False)
)
