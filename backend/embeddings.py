from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Sequence


_VECTOR_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "512"))
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text)]


def _bucket_for_token(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % _VECTOR_DIMENSION


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return vector

    return [value / magnitude for value in vector]


def _vectorize(text: str) -> list[float]:
    vector = [0.0] * _VECTOR_DIMENSION
    for token in _tokenize(text):
        vector[_bucket_for_token(token)] += 1.0
    return _normalize(vector)


@dataclass(slots=True)
class SimpleIndex:
    vectors: list[list[float]]

    @property
    def ntotal(self) -> int:
        return len(self.vectors)

    def search(self, query_vector: Sequence[float], top_k: int) -> tuple[list[list[float]], list[list[int]]]:
        if top_k <= 0 or not self.vectors:
            return [[]], [[]]

        scored_vectors: list[tuple[float, int]] = []
        for index, vector in enumerate(self.vectors):
            score = sum(float(a) * float(b) for a, b in zip(query_vector, vector))
            scored_vectors.append((score, index))

        scored_vectors.sort(key=lambda item: item[0], reverse=True)
        top_results = scored_vectors[:top_k]
        return [[score for score, _ in top_results]], [[index for _, index in top_results]]


def generate_embeddings(chunks: list[dict]) -> list[list[float]]:
    return [_vectorize(chunk.get("text", "")) for chunk in chunks]


def generate_query_embedding(question: str) -> list[float]:
    return _vectorize(question)


def create_faiss_index(embeddings: list[list[float]]) -> SimpleIndex:
    return SimpleIndex(vectors=[list(vector) for vector in embeddings])
