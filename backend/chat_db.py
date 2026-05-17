import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import Optional

DB_FILE = "chat_sessions.db"

def init_db():
    """Initialize SQLite database for chat sessions"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Chat sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            document_name TEXT NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Chat messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources TEXT,
            matched_paragraph TEXT,
            scope TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def create_session(session_id: str, doc_id: str, doc_name: str, title: Optional[str] = None):
    """Create a new chat session"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        INSERT INTO chat_sessions (session_id, document_id, document_name, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (session_id, doc_id, doc_name, title or f"Chat - {doc_name}", now, now))
    
    conn.commit()
    conn.close()

def save_message(message_id: str, session_id: str, role: str, content: str, sources=None, matched_paragraph=None, scope=None):
    """Save a chat message"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        INSERT INTO chat_messages (message_id, session_id, role, content, sources, matched_paragraph, scope, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        message_id, 
        session_id, 
        role, 
        content,
        json.dumps(sources) if sources else None,
        matched_paragraph,
        json.dumps(scope) if scope else None,
        now
    ))
    
    cursor.execute('UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?', (now, session_id))
    
    conn.commit()
    conn.close()

def get_sessions():
    """Get all chat sessions ordered by updated_at"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT session_id, document_id, document_name, title, created_at, updated_at
        FROM chat_sessions
        ORDER BY updated_at DESC
    ''')
    
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "session_id": row[0],
            "document_id": row[1],
            "document_name": row[2],
            "title": row[3],
            "created_at": row[4],
            "updated_at": row[5]
        })
    
    conn.close()
    return sessions

def get_session_messages(session_id: str):
    """Get all messages for a session"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT message_id, role, content, sources, matched_paragraph, scope, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
    ''', (session_id,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "sources": json.loads(row[3]) if row[3] else [],
            "matchedParagraph": row[4],
            "scope": json.loads(row[5]) if row[5] else None,
            "createdAt": row[6]
        })
    
    conn.close()
    return messages

def delete_session(session_id: str):
    """Delete a chat session and all its messages"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM chat_sessions WHERE session_id = ?', (session_id,))
    
    conn.commit()
    conn.close()

def update_session_title(session_id: str, title: str):
    """Update session title"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute('''
        UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?
    ''', (title, now, session_id))
    
    conn.commit()
    conn.close()
