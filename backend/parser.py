from __future__ import annotations

from dataclasses import dataclass
import os
import re

import fitz


@dataclass(slots=True)
class ParagraphRecord:
    file_name: str
    text: str
    page: int | None
    paragraph_index: int


def _split_paragraphs(text: str) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]
    if paragraphs:
        return paragraphs
    return [line.strip() for line in cleaned.split("\n") if line.strip()]


def extract_text_from_pdf(file_path: str) -> dict:
    document = fitz.open(file_path)
    extracted_pages = []
    metadata = document.metadata

    for page_number in range(len(document)):
        page = document.load_page(page_number)
        text = page.get_text()
        extracted_pages.append({"page": page_number + 1, "text": text})

    document.close()
    return {"metadata": metadata, "pages": extracted_pages}


def extract_text_from_txt(file_path: str) -> dict:
    extracted_pages = []

    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    extracted_pages.append({"page": 1, "text": text})

    return {"metadata": {"type": "txt"}, "pages": extracted_pages}


def parse_document(file_path: str) -> dict:
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)

    if extension == ".txt":
        return extract_text_from_txt(file_path)

    return {"error": "Unsupported file type"}


def extract_paragraphs(file_name: str, file_bytes: bytes) -> list[ParagraphRecord]:
    suffix = os.path.splitext(file_name)[1].lower()

    if suffix == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        paragraphs = _split_paragraphs(text)
        return [
            ParagraphRecord(file_name=file_name, text=paragraph, page=1, paragraph_index=index + 1)
            for index, paragraph in enumerate(paragraphs)
        ]

    if suffix == ".pdf":
        document = fitz.open(stream=file_bytes, filetype="pdf")
        records: list[ParagraphRecord] = []
        paragraph_index = 1

        for page_number in range(len(document)):
            page = document.load_page(page_number)
            for paragraph in _split_paragraphs(page.get_text()):
                records.append(
                    ParagraphRecord(
                        file_name=file_name,
                        text=paragraph,
                        page=page_number + 1,
                        paragraph_index=paragraph_index,
                    )
                )
                paragraph_index += 1

        document.close()
        return records

    raise ValueError("Only .txt and .pdf files are supported.")
