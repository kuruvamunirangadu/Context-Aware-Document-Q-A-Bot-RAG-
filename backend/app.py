from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .chunking import create_document_chunks
from .embeddings import create_faiss_index, generate_embeddings
from .llm import classify_scope, generate_answer
from .parser import extract_paragraphs
from .rag import retrieve_relevant_chunks
from .chat_db import init_db, create_session, save_message, get_sessions, get_session_messages, delete_session, update_session_title

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

# Initialize chat database
init_db()

# Logging setup for ask calls
LOGS_FOLDER = "logs"
os.makedirs(LOGS_FOLDER, exist_ok=True)
logger = logging.getLogger("rag_logger")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(os.path.join(LOGS_FOLDER, "ask_calls.log"))
fh.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
fh.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(fh)


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


class ChatSessionRequest(BaseModel):
    session_id: str
    doc_id: str
    doc_name: str


class SaveMessageRequest(BaseModel):
    session_id: str
    message_id: str
    role: str
    content: str
    sources: list | None = None
    matched_paragraph: str | None = None
    scope: dict | None = None


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

    # Structured logging for diagnosis: record question, scope, retrieved chunks, and answer
    try:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "doc_id": session.doc_id,
            "filename": session.filename,
            "question": request.question,
            "scope": scope,
            "retrieved_chunks": results,
            "sources": sources,
            "answer": answer,
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception:
        logger.exception("Failed to write ask log")

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": results,
        "doc_id": session.doc_id,
        "filename": session.filename,
        "scope": scope,
    }


@app.post("/sessions/create")
def create_chat_session(request: ChatSessionRequest):
    """Create a new chat session"""
    try:
        create_session(request.session_id, request.doc_id, request.doc_name)
        return {"success": True, "session_id": request.session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
def list_chat_sessions():
    """List all chat sessions"""
    try:
        sessions = get_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/messages")
def get_chat_messages(session_id: str):
    """Get all messages for a session"""
    try:
        messages = get_session_messages(session_id)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id}/messages")
def save_chat_message(session_id: str, request: SaveMessageRequest):
    """Save a message to a session"""
    try:
        save_message(
            request.message_id,
            session_id,
            request.role,
            request.content,
            request.sources,
            request.matched_paragraph,
            request.scope,
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
def delete_chat_session(session_id: str):
    """Delete a chat session and all its messages"""
    try:
        delete_session(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/sessions/{session_id}/title")
def update_chat_session_title(session_id: str, title: str):
    """Update session title"""
    try:
        update_session_title(session_id, title)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

