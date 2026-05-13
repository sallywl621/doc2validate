from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.repository_crawling.chunker import chunk_text
from src.repository_crawling.crawler import crawl_repository
from src.repository_crawling.html_parser import parse_html_to_text
from src.repository_crawling.normalizer import normalize_urls


class RepositoryExtractor:
    def __init__(
        self,
        max_depth: int = 2,
        chunk_size: int = 1000,
        max_pages_per_domain: int = 20,
    ):
        self.max_depth = max_depth
        self.chunk_size = chunk_size
        self.max_pages_per_domain = max_pages_per_domain

    def extract(
        self,
        article_id: str,
        repository_urls: list[str],
        output_dir: str | Path,
    ) -> dict:
        """
        Build scraped repository evidence for one article.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        norm_urls = normalize_urls(repository_urls)

        pages = crawl_repository(
            root_urls=norm_urls,
            max_depth=self.max_depth,
            max_pages_per_domain=self.max_pages_per_domain,
        )

        chunks = []
        chunk_index = 1

        for page in pages:
            text = parse_html_to_text(page["html"])

            if not text.strip():
                continue

            page_chunks = chunk_text(
                text=text,
                chunk_size=self.chunk_size,
                base_index=chunk_index,
                source_url=page["url"],
            )

            chunks.extend(page_chunks)
            chunk_index += len(page_chunks)

        result = {
            "metadata": {
                "article_id": article_id,
                "source_type": "Scraped Repository",
                "root_urls": norm_urls,
                "crawl_depth": self.max_depth,
                "page_count": len(pages),
            },
            "chunks": chunks,
            "processing_info": {
                "processing_time": datetime.utcnow().isoformat(),
                "source": "Scraped Repository",
                "chunk_size": self.chunk_size,
            },
        }

        out_path = output_dir / "scraped_repository.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return result
