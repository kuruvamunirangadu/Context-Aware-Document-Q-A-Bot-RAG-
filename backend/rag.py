from __future__ import annotations

import faiss
import re
from difflib import SequenceMatcher

from embeddings import generate_query_embedding


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
}


def _tokenize(text: str) -> set[str]:
    tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9']+", text)}
    return {token for token in tokens if token not in _STOPWORDS and len(token) > 1}


def _best_fuzzy_match(term: str, candidates: set[str]) -> float:
    if not candidates:
        return 0.0

    best_score = 0.0
    for candidate in candidates:
        score = SequenceMatcher(None, term, candidate).ratio()
        if score > best_score:
            best_score = score
            if best_score >= 1.0:
                break

    return best_score


def _lexical_overlap(question_terms: set[str], chunk_terms: set[str]) -> float:
    if not question_terms:
        return 0.0

    matched_terms = 0
    for term in question_terms:
        if term in chunk_terms:
            matched_terms += 1
            continue

        if _best_fuzzy_match(term, chunk_terms) >= 0.86:
            matched_terms += 1

    return matched_terms / len(question_terms)


def _combined_score(semantic_score: float, lexical_overlap: float, question: str, chunk_text: str) -> float:
    combined = (max(0.0, semantic_score) * 0.7) + (lexical_overlap * 0.3)

    normalized_question = " ".join(question.lower().split())
    normalized_chunk = " ".join(chunk_text.lower().split())
    if normalized_question and normalized_question in normalized_chunk:
        combined += 0.1

    lines = [line.strip() for line in chunk_text.splitlines() if line.strip()]
    toc_like_lines = sum(1 for line in lines if re.search(r"\.\.{2,}|\s\d{1,4}$", line))
    if toc_like_lines >= 2:
        combined -= 0.18
    elif toc_like_lines == 1:
        combined -= 0.08

    if len(lines) <= 3 and any(len(line.split()) <= 6 for line in lines):
        combined += 0.04

    return min(1.0, combined)


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

    candidate_k = min(len(chunks), int(index.ntotal))
    if candidate_k <= 0:
        return []

    query_embedding = generate_query_embedding(question)
    similarities, indices = index.search(query_embedding, candidate_k)

    question_terms = _tokenize(question)
    ranked_candidates: list[tuple[float, float, dict]] = []

    for i in range(candidate_k):
        chunk_index = int(indices[0][i])
        if chunk_index < 0 or chunk_index >= len(chunks):
            continue

        semantic_score = float(similarities[0][i])
        retrieved_chunk = chunks[chunk_index]
        chunk_text = retrieved_chunk.get("paragraph_text", retrieved_chunk.get("text", ""))
        chunk_terms = _tokenize(chunk_text)
        lexical_overlap = _lexical_overlap(question_terms, chunk_terms)
        combined_score = _combined_score(semantic_score, lexical_overlap, question, chunk_text)

        ranked_candidates.append(
            (
                combined_score,
                semantic_score,
                {
                    "chunk_id": retrieved_chunk.get("chunk_id"),
                    "page": retrieved_chunk.get("page"),
                    "text": retrieved_chunk.get("text", ""),
                    "paragraph_text": chunk_text,
                    "paragraph_index": retrieved_chunk.get("paragraph_index"),
                    "paragraph_chunk_index": retrieved_chunk.get("paragraph_chunk_index"),
                    "score": round(combined_score, 4),
                    "confidence": calculate_confidence(combined_score),
                },
            )
        )

    ranked_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [candidate[2] for candidate in ranked_candidates[:safe_top_k]]
