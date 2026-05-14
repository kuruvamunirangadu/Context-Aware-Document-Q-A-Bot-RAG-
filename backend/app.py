from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chunking import create_document_chunks
from embeddings import create_faiss_index, generate_embeddings
from llm import classify_scope, generate_answer
from parser import extract_paragraphs
from rag import retrieve_relevant_chunks

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@dataclass(slots=True)
class DocumentSession:
    doc_id: str
    filename: str
    chunks: list[dict]
    vector_index: object
    total_chunks: int
    created_at: str


document_sessions: dict[str, DocumentSession] = {}
active_document_id: str | None = None


class QuestionRequest(BaseModel):
    question: str
    doc_id: str | None = None


@app.get("/")
def home():
    return {"message": "Backend Running Successfully"}


@app.get("/documents")
def list_documents():
    documents = [
        {
            "doc_id": session.doc_id,
            "filename": session.filename,
            "total_chunks": session.total_chunks,
            "created_at": session.created_at,
        }
        for session in document_sessions.values()
    ]
    return {"documents": documents, "active_document_id": active_document_id}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global active_document_id

    allowed_extensions = [".pdf", ".txt"]

    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed")

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file_bytes = await file.read()

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    paragraph_records = extract_paragraphs(file.filename, file_bytes)

    chunks = create_document_chunks(paragraph_records)

    embeddings = generate_embeddings(chunks)
    index = create_faiss_index(embeddings)

    doc_id = uuid4().hex
    document_sessions[doc_id] = DocumentSession(
        doc_id=doc_id,
        filename=file.filename,
        chunks=chunks,
        vector_index=index,
        total_chunks=len(chunks),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    active_document_id = doc_id

    return {
        "message": "Document processed successfully",
        "doc_id": doc_id,
        "filename": file.filename,
        "total_chunks": len(chunks),
        "embedding_dimension": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0,
        "vectors_stored": int(index.ntotal),
    }


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    global active_document_id

    doc_id = request.doc_id or active_document_id
    if not doc_id:
        raise HTTPException(status_code=400, detail="Please upload a document first")

    session = document_sessions.get(doc_id)
    if session is None:
        raise HTTPException(status_code=400, detail="Selected document session is no longer available")

    results = retrieve_relevant_chunks(
        request.question,
        session.vector_index,
        session.chunks,
        top_k=3,
    )

    scope = classify_scope(request.question, results)
    answer = generate_answer(request.question, results)

    sources = []
    for chunk in results:
        sources.append(
            {
                "page": chunk.get("page"),
                "chunk_id": chunk.get("chunk_id"),
                "confidence": chunk.get("confidence", 0),
                "score": chunk.get("score", 0),
                "paragraph_index": chunk.get("paragraph_index"),
                "paragraph_text": chunk.get("paragraph_text", ""),
            }
        )

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": results,
        "doc_id": session.doc_id,
        "filename": session.filename,
        "scope": scope,
    }

