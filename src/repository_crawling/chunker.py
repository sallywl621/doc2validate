from __future__ import annotations


def chunk_text(
    text: str,
    chunk_size: int,
    base_index: int,
    source_url: str,
) -> list[dict]:
    chunks = []
    start = 0
    idx = base_index

    while start < len(text):
        current_chunk = text[start : start + chunk_size]

        chunks.append(
            {
                "sectitle": "Scraped Repository",
                "text": current_chunk,
                "chunk_index": idx,
                "source_url": source_url,
            }
        )

        idx += 1
        start += chunk_size

    return chunks
