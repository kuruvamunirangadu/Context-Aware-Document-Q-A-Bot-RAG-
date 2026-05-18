from __future__ import annotations

from collections.abc import Iterable
import re

from .parser import ParagraphRecord


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    words = text.split()
    chunks: list[dict] = []
    start = 0
    chunk_id = 1

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words)

        chunks.append({"chunk_id": chunk_id, "text": chunk})

        start += chunk_size - overlap
        chunk_id += 1

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]
    if paragraphs:
        return paragraphs
    return [line.strip() for line in cleaned.split("\n") if line.strip()]


def _iter_paragraph_records(parsed_data: object) -> Iterable[ParagraphRecord]:
    if isinstance(parsed_data, list):
        for record in parsed_data:
            if isinstance(record, ParagraphRecord):
                yield record
        return

    if isinstance(parsed_data, dict):
        for page_data in parsed_data.get("pages", []):
            page_number = page_data.get("page")
            text = page_data.get("text", "")
            for paragraph_index, paragraph in enumerate(_split_paragraphs(text), start=1):
                yield ParagraphRecord(
                    file_name=str(parsed_data.get("metadata", {}).get("title", "document")),
                    text=paragraph,
                    page=page_number,
                    paragraph_index=paragraph_index,
                )


def create_document_chunks(parsed_data: object) -> list[dict]:
    all_chunks: list[dict] = []
    global_chunk_id = 1

    for paragraph_record in _iter_paragraph_records(parsed_data):
        paragraph_text = paragraph_record.text.strip()
        if not paragraph_text:
            continue

        paragraph_chunks = chunk_text(paragraph_text)

        for paragraph_chunk_index, chunk in enumerate(paragraph_chunks, start=1):
            all_chunks.append(
                {
                    "chunk_id": global_chunk_id,
                    "page": paragraph_record.page,
                    "text": chunk["text"],
                    "paragraph_text": paragraph_text,
                    "paragraph_index": paragraph_record.paragraph_index,
                    "paragraph_chunk_index": paragraph_chunk_index,
                    "file_name": paragraph_record.file_name,
                }
            )
            global_chunk_id += 1

    return all_chunks
