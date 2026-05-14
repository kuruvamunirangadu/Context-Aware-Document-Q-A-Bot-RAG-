from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv


_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_BACKEND_DIR / ".env", override=False)
load_dotenv(dotenv_path=_BACKEND_DIR.parent / ".env", override=False)

MIN_CONFIDENCE_FOR_LLM = float(os.getenv("MIN_CONFIDENCE_FOR_LLM", "30"))

_MODEL = None
_CLIENT = None


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

    if not retrieved_chunks:
        return "Answer not found in document."

    best_confidence = float(retrieved_chunks[0].get("confidence", 0))
    if best_confidence < MIN_CONFIDENCE_FOR_LLM:
        return "Answer not found in document."

    context_blocks: list[str] = []
    for chunk in retrieved_chunks:
        page = chunk.get("page", "unknown")
        text = chunk.get("text", "")
        context_blocks.append(f"Page: {page}\nContent:\n{text}")
    context = "\n\n".join(context_blocks)

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
