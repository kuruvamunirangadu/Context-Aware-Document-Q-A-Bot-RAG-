from __future__ import annotations

import os
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
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

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create {UPLOAD_FOLDER}: {e}")

# Initialize chat database
try:
    init_db()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")

# Logging setup for ask calls: always log to stdout; attempt file logging when writable
LOGS_FOLDER = "logs"
logger = logging.getLogger("rag_logger")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

# Stream handler to stdout (captured by Vercel)
try:
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)
    # Avoid adding duplicate handlers on reload
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(sh)
except Exception as e:
    # If stdout handler fails (very unlikely), fall back to no-op
    print(f"Warning: Could not set up stdout logging: {e}")

# Try to add a file handler if filesystem is writable
try:
    os.makedirs(LOGS_FOLDER, exist_ok=True)
    fh = logging.FileHandler(os.path.join(LOGS_FOLDER, "ask_calls.log"))
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        logger.addHandler(fh)
except Exception as e:
    print(f"Warning: Could not set up file logging: {e}")


def log_event(event: str, **fields: object) -> None:
    try:
        logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False))
    except Exception:
        logger.exception("Failed to write backend log event")


@dataclass(slots=True)
class DocumentSession:
    doc_id: str
    filename: str
    chunks: list[dict]
    vector_index: object | None
    total_chunks: int
    created_at: str
    status: str = "ready"
    error: str | None = None
    file_size: int = 0


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


@app.get("/health")
def health():
    return {"status": "ok", "message": "Backend Running Successfully"}


@app.get("/documents")
def list_documents():
    documents = [
        {
            "doc_id": session.doc_id,
            "filename": session.filename,
            "total_chunks": session.total_chunks,
            "created_at": session.created_at,
            "status": session.status,
            "error": session.error,
            "file_size": session.file_size,
        }
        for session in document_sessions.values()
    ]
    return {"documents": documents, "active_document_id": active_document_id}


@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    session = document_sessions.get(doc_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "doc_id": session.doc_id,
        "filename": session.filename,
        "total_chunks": session.total_chunks,
        "created_at": session.created_at,
        "status": session.status,
        "error": session.error,
        "file_size": session.file_size,
    }


def process_document_upload(doc_id: str, filename: str, file_bytes: bytes) -> None:
    started_at = time.perf_counter()
    session = document_sessions.get(doc_id)
    if session is None:
        log_event("upload_session_missing", filename=filename, doc_id=doc_id)
        return

    try:
        paragraph_records = extract_paragraphs(filename, file_bytes)
        log_event("upload_paragraphs_extracted", filename=filename, doc_id=doc_id, paragraphs=len(paragraph_records))

        chunks = create_document_chunks(paragraph_records)
        log_event("upload_chunks_created", filename=filename, doc_id=doc_id, chunks=len(chunks))

        if not chunks:
            raise ValueError("No readable text was found in this document")

        embeddings = generate_embeddings(chunks)
        log_event(
            "upload_embeddings_generated",
            filename=filename,
            doc_id=doc_id,
            embeddings=len(embeddings),
            dimension=len(embeddings[0]) if embeddings else 0,
        )

        index = create_faiss_index(embeddings)
        log_event("upload_index_created", filename=filename, doc_id=doc_id, vectors=int(index.ntotal))

        session.chunks = chunks
        session.vector_index = index
        session.total_chunks = len(chunks)
        session.status = "ready"
        session.error = None

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event("upload_completed", filename=filename, doc_id=doc_id, duration_ms=duration_ms)
    except Exception as exc:
        session.status = "failed"
        session.error = str(exc)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception("Document processing failed for %s after %sms", filename, duration_ms)
        log_event("upload_failed", filename=filename, doc_id=doc_id, duration_ms=duration_ms, error=str(exc))


@app.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    global active_document_id

    started_at = time.perf_counter()
    allowed_extensions = [".pdf", ".txt"]
    filename = os.path.basename(file.filename or "")

    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed")

    log_event(
        "upload_received",
        filename=filename,
        content_type=file.content_type,
        extension=file_extension,
    )

    try:
        file_bytes = await file.read()
        read_duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event("upload_read", filename=filename, bytes=len(file_bytes), duration_ms=read_duration_ms)

        doc_id = uuid4().hex
        document_sessions[doc_id] = DocumentSession(
            doc_id=doc_id,
            filename=filename,
            chunks=[],
            vector_index=None,
            total_chunks=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="processing",
            file_size=len(file_bytes),
        )
        active_document_id = doc_id
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event("upload_accepted", filename=filename, doc_id=doc_id, duration_ms=duration_ms)
        background_tasks.add_task(process_document_upload, doc_id, filename, file_bytes)

        return {
            "message": "Document upload accepted. Processing started.",
            "doc_id": doc_id,
            "filename": filename,
            "total_chunks": 0,
            "status": "processing",
            "vectors_stored": 0,
        }
    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception("Document upload failed for %s after %sms", filename, duration_ms)
        raise HTTPException(status_code=500, detail=f"Upload failed while processing {filename}: {exc}") from exc


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    global active_document_id

    doc_id = request.doc_id or active_document_id
    if not doc_id:
        raise HTTPException(status_code=400, detail="Please upload a document first")

    session = document_sessions.get(doc_id)
    if session is None:
        raise HTTPException(status_code=400, detail="Selected document session is no longer available")
    if session.status == "processing":
        raise HTTPException(status_code=409, detail="Document is still processing. Please try again in a moment.")
    if session.status == "failed":
        raise HTTPException(status_code=400, detail=session.error or "Document processing failed")
    if session.vector_index is None:
        raise HTTPException(status_code=400, detail="Document index is not available")

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
