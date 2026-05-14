from __future__ import annotations

import faiss
import numpy as np
from sklearn.preprocessing import normalize
from sentence_transformers import SentenceTransformer


_MODEL: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def generate_embeddings(chunks: list[dict]) -> np.ndarray:
    model = _get_model()
    texts = [chunk["text"] for chunk in chunks if chunk.get("text")]
    if not texts:
        dim = model.get_sentence_embedding_dimension()
        return np.empty((0, dim), dtype="float32")

    embeddings = model.encode(texts)
    normalized_embeddings = normalize(np.array(embeddings).astype("float32"))
    return normalized_embeddings


def generate_query_embedding(question: str) -> np.ndarray:
    model = _get_model()
    query_embedding = model.encode([question])
    normalized_query_embedding = normalize(np.array(query_embedding).astype("float32"))
    return normalized_query_embedding


def create_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    if embeddings.ndim != 2:
        raise ValueError("Embeddings must be a 2D array")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)

    if embeddings.shape[0] > 0:
        index.add(embeddings)

    return index
