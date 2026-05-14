from __future__ import annotations

import os
import shutil

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chunking import create_document_chunks
from embeddings import create_faiss_index, generate_embeddings
from llm import generate_answer
from parser import parse_document
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

document_chunks: list[dict] = []
vector_index = None


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "Backend Running Successfully"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global document_chunks, vector_index

    allowed_extensions = [".pdf", ".txt"]

    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        return {"error": "Only PDF and TXT files are allowed"}

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Parse document
    parsed_data = parse_document(file_path)

    # Create chunks
    chunks = create_document_chunks(parsed_data)

    # Generate embeddings
    embeddings = generate_embeddings(chunks)

    # Create vector database
    index = create_faiss_index(embeddings)

    document_chunks = chunks
    vector_index = index

    return {
        "message": "Document processed successfully",
        "filename": file.filename,
        "total_chunks": len(chunks),
        "embedding_dimension": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0,
        "vectors_stored": int(index.ntotal),
    }


@app.post("/ask")
async def ask_question(request: QuestionRequest):
    global document_chunks, vector_index

    if vector_index is None:
        return {"error": "Please upload a document first"}

    results = retrieve_relevant_chunks(
        request.question,
        vector_index,
        document_chunks,
        top_k=3,
    )

    answer = generate_answer(request.question, results)

    sources = []
    for chunk in results:
        sources.append(
            {
                "page": chunk.get("page"),
                "chunk_id": chunk.get("chunk_id"),
                "confidence": chunk.get("confidence", 0),
            }
        )

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": results,
    }

