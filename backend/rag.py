from __future__ import annotations

import faiss

from embeddings import generate_query_embedding


def calculate_confidence(distance: float) -> float:
    confidence = 1 / (1 + distance)
    return round(confidence * 100, 2)


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
    distances, indices = index.search(query_embedding, safe_top_k)

    results: list[dict] = []
    for i in range(safe_top_k):
        chunk_index = int(indices[0][i])
        if chunk_index < 0 or chunk_index >= len(chunks):
            continue

        distance = float(distances[0][i])
        retrieved_chunk = chunks[chunk_index]
        confidence = calculate_confidence(distance)
        results.append(
            {
                "chunk_id": retrieved_chunk.get("chunk_id"),
                "page": retrieved_chunk.get("page"),
                "text": retrieved_chunk.get("text", ""),
                "distance": round(distance, 4),
                "confidence": confidence,
            }
        )

    return results
