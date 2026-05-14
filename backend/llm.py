from __future__ import annotations

import os
import re
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv


_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_BACKEND_DIR / ".env", override=False)
load_dotenv(dotenv_path=_BACKEND_DIR.parent / ".env", override=False)

MIN_SIMILARITY_FOR_ANSWER = float(os.getenv("MIN_SIMILARITY_FOR_ANSWER", "0.28"))
MIN_OVERLAP_FOR_ANSWER = float(os.getenv("MIN_OVERLAP_FOR_ANSWER", "0.15"))
MIN_SUPPORTING_CHUNKS = int(os.getenv("MIN_SUPPORTING_CHUNKS", "1"))

_MODEL = None
_CLIENT = None

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
    "how",
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


def _build_context_blocks(retrieved_chunks: list[dict]) -> list[str]:
    context_blocks: list[str] = []

    for chunk in retrieved_chunks:
        page = chunk.get("page", "unknown")
        paragraph_index = chunk.get("paragraph_index", "unknown")
        paragraph_text = chunk.get("paragraph_text", chunk.get("text", ""))
        chunk_text = chunk.get("text", "")
        context_blocks.append(
            f"Page: {page}\nParagraph: {paragraph_index}\nParagraph text:\n{paragraph_text}\nChunk text:\n{chunk_text}"
        )

    return context_blocks


def classify_scope(question: str, retrieved_chunks: list[dict]) -> dict[str, object]:
    if len(retrieved_chunks) < MIN_SUPPORTING_CHUNKS:
        return {
            "in_scope": False,
            "reason": "No supporting chunks were retrieved.",
            "top_score": 0.0,
            "overlap": 0.0,
        }

    top_chunk = retrieved_chunks[0]
    top_score = float(top_chunk.get("score", top_chunk.get("confidence", 0) / 100.0))

    question_terms = _tokenize(question)
    if not question_terms:
        return {
            "in_scope": False,
            "reason": "The question does not contain enough searchable terms.",
            "top_score": round(top_score, 4),
            "overlap": 0.0,
        }

    context_text = " ".join(
        str(chunk.get("paragraph_text", chunk.get("text", ""))) for chunk in retrieved_chunks[:3]
    )
    context_terms = _tokenize(context_text)
    overlap = len(question_terms & context_terms) / max(len(question_terms), 1)

    if top_score >= MIN_SIMILARITY_FOR_ANSWER:
        return {
            "in_scope": True,
            "reason": "Top retrieval score is strong enough.",
            "top_score": round(top_score, 4),
            "overlap": round(overlap, 4),
        }

    if overlap >= 0.5 and top_score >= 0.1:
        return {
            "in_scope": True,
            "reason": "The retrieved paragraph contains the same key term as the question.",
            "top_score": round(top_score, 4),
            "overlap": round(overlap, 4),
        }

    if overlap >= MIN_OVERLAP_FOR_ANSWER and top_score >= (MIN_SIMILARITY_FOR_ANSWER * 0.8):
        return {
            "in_scope": True,
            "reason": "Question terms overlap with the retrieved paragraph.",
            "top_score": round(top_score, 4),
            "overlap": round(overlap, 4),
        }

    return {
        "in_scope": False,
        "reason": "Retrieved content does not sufficiently match the question.",
        "top_score": round(top_score, 4),
        "overlap": round(overlap, 4),
    }


def _get_client() -> OpenAI | None:
    global _CLIENT

    if _CLIENT is not None:
        return _CLIENT

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT


def generate_answer(question: str, retrieved_chunks: list[dict]) -> str:
    client = _get_client()
    if client is None:
        return "LLM is not configured. Set OPENAI_API_KEY to generate answers."

    scope = classify_scope(question, retrieved_chunks)
    if not scope["in_scope"]:
        return "Answer not found in document."

    context = "\n\n".join(_build_context_blocks(retrieved_chunks))

    prompt = f"""
You are a document question answering assistant.

Answer ONLY using the provided context.

If the answer is not available in the context,
say exactly:
"Answer not found in document."

Context:
{context}

Question:
{question}

Answer:
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Answer only from the supplied document context."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
    except Exception:
        return "Answer not found in document."

    text = (response.choices[0].message.content or "").strip()
    if not text:
        return "Answer not found in document."
    return text
