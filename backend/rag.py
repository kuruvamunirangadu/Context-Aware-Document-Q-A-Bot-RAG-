from __future__ import annotations

import faiss

from embeddings import generate_query_embedding


def calculate_confidence(similarity: float) -> float:
    confidence = max(0.0, similarity) * 100
    return round(confidence, 2)


def retrieve_relevant_chunks(
    question: str,
    index: faiss.Index,
    chunks: list[dict],
    top_k: int = 3,
) -> list[dict]:
    if not question.strip() or not chunks or index.ntotal == 0:
        return []

    safe_top_k = min(top_k, len(chunks), int(index.ntotal))
    if safe_top_k <= 0:
        return []

    query_embedding = generate_query_embedding(question)
    similarities, indices = index.search(query_embedding, safe_top_k)

    results: list[dict] = []
    for i in range(safe_top_k):
        chunk_index = int(indices[0][i])
        if chunk_index < 0 or chunk_index >= len(chunks):
            continue

        similarity = float(similarities[0][i])
        retrieved_chunk = chunks[chunk_index]
        confidence = calculate_confidence(similarity)
        results.append(
            {
                "chunk_id": retrieved_chunk.get("chunk_id"),
                "page": retrieved_chunk.get("page"),
                "text": retrieved_chunk.get("text", ""),
                "paragraph_text": retrieved_chunk.get("paragraph_text", retrieved_chunk.get("text", "")),
                "paragraph_index": retrieved_chunk.get("paragraph_index"),
                "paragraph_chunk_index": retrieved_chunk.get("paragraph_chunk_index"),
                "score": round(similarity, 4),
                "confidence": confidence,
            }
        )

    return results
