from __future__ import annotations

import argparse
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


class SimpleTextSplitter:
    """A lightweight sentence-based text splitter."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 300):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        sentences = re.split(r"(?<=[。！？.!?])\s+", text)

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk + sentence) <= self.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                if self.chunk_overlap > 0 and chunks:
                    last_chunk = chunks[-1]
                    overlap_words = last_chunk.split()[-self.chunk_overlap // 4 :]
                    current_chunk = " ".join(overlap_words) + " " + sentence + " "
                else:
                    current_chunk = sentence + " "

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True,
    )


def check_grobid_alive(grobid_url: str = "http://localhost:8070") -> bool:
    """Check whether the GROBID service is alive."""
    try:
        response = requests.get(f"{grobid_url}/api/isalive", timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def grobid_parse_pdf_to_dict(
    file_path: Path | str,
    grobid_url: str = "http://localhost:8070",
    timeout: int = 90,
) -> Optional[Dict[str, Any]]:
    """Send one PDF to GROBID and parse the returned TEI XML."""
    file_path = Path(file_path)

    try:
        with file_path.open("rb") as pdf_file:
            files = {"input": pdf_file}
            response = requests.post(
                f"{grobid_url}/api/processFulltextDocument",
                files=files,
                timeout=timeout,
            )

        if response.status_code != 200:
            logging.warning(
                "GROBID request failed for %s: status=%s",
                file_path,
                response.status_code,
            )
            return None

        return parse_grobid_xml_to_dict(response.text)

    except Exception as exc:
        logging.warning("GROBID parsing error for %s: %s", file_path, exc)
        return None


def parse_grobid_xml_to_dict(xml_content: str) -> Optional[Dict[str, Any]]:
    """Parse GROBID TEI XML into a normalized dictionary."""
    try:
        root = ET.fromstring(xml_content)
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}

        article_dict: Dict[str, Any] = {
            "title": "",
            "authors": "",
            "abstract": "",
            "doi": "",
            "sections": [],
            "figures": [],
        }

        title_elem = root.find(".//tei:titleStmt/tei:title", ns)
        if title_elem is not None and title_elem.text:
            article_dict["title"] = title_elem.text.strip()

        authors = []
        for author_elem in root.findall(".//tei:author", ns):
            author_name = extract_author_name(author_elem, ns)
            if author_name:
                authors.append(author_name)
        article_dict["authors"] = ", ".join(authors)

        abstract_elem = root.find(".//tei:profileDesc/tei:abstract", ns)
        if abstract_elem is not None:
            article_dict["abstract"] = extract_element_text(abstract_elem)

        doi_elem = root.find(".//tei:publicationStmt/tei:idno[@type='DOI']", ns)
        if doi_elem is not None and doi_elem.text:
            article_dict["doi"] = doi_elem.text.strip()
        else:
            doi_elems = root.findall(".//tei:idno[@type='DOI']", ns)
            if doi_elems and doi_elems[0].text:
                article_dict["doi"] = doi_elems[0].text.strip()

        article_dict["sections"] = extract_sections(root, ns)
        article_dict["figures"] = extract_figures(root, ns)

        return article_dict

    except Exception as exc:
        logging.warning("Failed to parse GROBID XML: %s", exc)
        return None


def extract_author_name(author_elem: ET.Element, ns: Dict[str, str]) -> str:
    pers_name = author_elem.find("tei:persName", ns)
    if pers_name is None:
        return ""

    forename = pers_name.find("tei:forename", ns)
    surname = pers_name.find("tei:surname", ns)

    forename_text = forename.text.strip() if forename is not None and forename.text else ""
    surname_text = surname.text.strip() if surname is not None and surname.text else ""

    return f"{forename_text} {surname_text}".strip()


def extract_element_text(element: ET.Element) -> str:
    text_parts: List[str] = []

    if element.text and element.text.strip():
        text_parts.append(element.text.strip())

    for child in element:
        if child.text and child.text.strip():
            text_parts.append(child.text.strip())
        if child.tail and child.tail.strip():
            text_parts.append(child.tail.strip())

    return " ".join(text_parts)


def extract_sections(root: ET.Element, ns: Dict[str, str]) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    body_elem = root.find(".//tei:text/tei:body", ns)

    if body_elem is None:
        return sections

    for div in body_elem.findall(".//tei:div", ns):
        heading_elem = div.find("tei:head", ns)
        heading = (
            heading_elem.text.strip()
            if heading_elem is not None and heading_elem.text
            else "Untitled"
        )

        section_text_parts = []
        for paragraph in div.findall(".//tei:p", ns):
            paragraph_text = extract_element_text(paragraph)
            if paragraph_text:
                section_text_parts.append(paragraph_text)

        section_text = "\n\n".join(section_text_parts).strip()

        if section_text:
            sections.append(
                {
                    "heading": heading,
                    "text": section_text,
                }
            )

    return sections


def extract_figures(root: ET.Element, ns: Dict[str, str]) -> List[Dict[str, str]]:
    figures: List[Dict[str, str]] = []

    for figure_elem in root.findall(".//tei:figure", ns):
        label_elem = figure_elem.find("tei:label", ns)
        caption_elem = figure_elem.find("tei:figDesc", ns)

        figure_label = label_elem.text.strip() if label_elem is not None and label_elem.text else ""
        figure_caption = (
            caption_elem.text.strip()
            if caption_elem is not None and caption_elem.text
            else ""
        )

        figure_type = "table" if figure_elem.find(".//tei:table", ns) is not None else "figure"

        figures.append(
            {
                "figure_label": figure_label,
                "figure_caption": figure_caption,
                "figure_type": figure_type,
            }
        )

    return figures


def get_references_from_crossref(
    doi: str,
    timeout: int = 30,
) -> List[str]:
    """Fetch reference strings from CrossRef."""
    if not doi:
        return []

    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    url = f"https://api.crossref.org/works/{doi}"

    try:
        response = requests.get(url, timeout=timeout)

        if response.status_code != 200:
            logging.warning(
                "CrossRef request failed for DOI %s: status=%s",
                doi,
                response.status_code,
            )
            return []

        data = response.json()
        message = data.get("message", {})
        reference_list = message.get("reference", [])
        reference_count = message.get("reference-count", 0)

        if reference_count and len(reference_list) != reference_count:
            logging.info(
                "CrossRef reference count mismatch for DOI %s: reported=%s parsed=%s",
                doi,
                reference_count,
                len(reference_list),
            )

        references = []
        for index, ref_data in enumerate(reference_list, start=1):
            reference_text = extract_reference_text(ref_data, index)
            if reference_text:
                references.append(reference_text)

        return references

    except Exception as exc:
        logging.warning("Failed to fetch CrossRef references for DOI %s: %s", doi, exc)
        return []


def extract_reference_text(ref_data: Dict[str, Any], index: int) -> str:
    """Extract one readable reference string from CrossRef reference metadata."""
    if ref_data.get("unstructured"):
        return f"{index}. {ref_data['unstructured'].strip()}"

    parts: List[str] = []

    if ref_data.get("author"):
        parts.append(str(ref_data["author"]))

    if ref_data.get("article-title"):
        parts.append(f"\"{ref_data['article-title']}\"")
    elif ref_data.get("title"):
        parts.append(f"\"{ref_data['title']}\"")

    if ref_data.get("journal-title"):
        parts.append(str(ref_data["journal-title"]))

    if ref_data.get("year"):
        parts.append(f"({ref_data['year']})")

    if ref_data.get("DOI"):
        parts.append(f"DOI: {ref_data['DOI']}")

    if parts:
        return f"{index}. " + " ".join(parts)

    fallback_parts = []
    for key, value in ref_data.items():
        if key != "key" and value:
            fallback_parts.append(f"{key}: {value}")

    if fallback_parts:
        return f"{index}. " + "; ".join(fallback_parts[:3])

    return f"{index}. Reference information not available"


def parse_pdf_to_json(
    file_path: Path | str,
    grobid_url: str = "http://localhost:8070",
    include_crossref_references: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Parse one PDF into a structured JSON-like dictionary.

    Output format:
        {
            "metadata": {...},
            "chunks": [
                {"sectitle": "Title", "text": "..."},
                {"sectitle": "Abstract", "text": "..."},
                ...
                {"sectitle": "REFERENCES", "text": "..."}
            ]
        }
    """
    file_path = Path(file_path)

    article_dict = grobid_parse_pdf_to_dict(
        file_path=file_path,
        grobid_url=grobid_url,
    )

    if article_dict is None:
        logging.warning("PDF was not parsed: %s", file_path)
        return None

    chunks: List[Dict[str, str]] = []

    chunks.append(
        {
            "sectitle": "Title",
            "text": f"Title: {article_dict['title']}\n\nAuthors: {article_dict['authors']}",
        }
    )

    chunks.append(
        {
            "sectitle": "Abstract",
            "text": f"Abstract: {article_dict['abstract']}",
        }
    )

    for section in article_dict["sections"]:
        heading = section["heading"].rstrip(".")
        chunks.append(
            {
                "sectitle": heading,
                "text": section["text"],
            }
        )

    if include_crossref_references:
        doi = article_dict.get("doi", "")
        references = get_references_from_crossref(doi) if doi else []

        if references:
            reference_text = "REFERENCES:\n\n" + "\n".join(references)
        elif doi:
            reference_text = "REFERENCES: No references available from CrossRef."
        else:
            reference_text = "REFERENCES: No DOI available to fetch references."

        chunks.append(
            {
                "sectitle": "REFERENCES",
                "text": reference_text,
            }
        )

    for figure in article_dict["figures"]:
        label = figure.get("figure_label", "")
        caption = figure.get("figure_caption", "")
        figure_type = figure.get("figure_type", "figure")

        if figure_type == "table":
            text = f"In table {label} of the document we can see: {caption}"
            sectitle = f"Table {label}"
        else:
            text = f"In figure {label} of the document we can see: {caption}"
            sectitle = f"Figure {label}"

        chunks.append(
            {
                "sectitle": sectitle,
                "text": text,
            }
        )

    result = {
        "metadata": {
            "title": article_dict["title"],
            "authors": article_dict["authors"],
            "doi": article_dict.get("doi", ""),
            "abstract": article_dict["abstract"],
            "section_count": len(article_dict["sections"]),
            "figure_count": len(article_dict["figures"]),
            "total_chunks": len(chunks),
            "reference_source": "CrossRef" if include_crossref_references else "",
        },
        "chunks": chunks,
    }

    logging.info("Parsed PDF into %d chunks: %s", len(chunks), file_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse one PDF into structured JSON.")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--grobid-url", type=str, default="http://localhost:8070")
    parser.add_argument("--no-crossref", action="store_true")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    if not check_grobid_alive(args.grobid_url):
        logging.warning("GROBID service does not appear to be alive: %s", args.grobid_url)

    result = parse_pdf_to_json(
        file_path=args.pdf,
        grobid_url=args.grobid_url,
        include_crossref_references=not args.no_crossref,
    )

    if result is None:
        raise RuntimeError(f"Failed to parse PDF: {args.pdf}")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    logging.info("Wrote structured JSON to %s", args.output)


if __name__ == "__main__":
    main()
