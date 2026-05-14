from __future__ import annotations


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


def create_document_chunks(parsed_data: dict) -> list[dict]:
    all_chunks: list[dict] = []
    global_chunk_id = 1

    for page_data in parsed_data.get("pages", []):
        page_number = page_data.get("page")
        text = page_data.get("text", "")

        page_chunks = chunk_text(text)

        for chunk in page_chunks:
            all_chunks.append(
                {
                    "chunk_id": global_chunk_id,
                    "page": page_number,
                    "text": chunk["text"],
                    "metadata": parsed_data.get("metadata", {}),
                }
            )
            global_chunk_id += 1

    return all_chunks
