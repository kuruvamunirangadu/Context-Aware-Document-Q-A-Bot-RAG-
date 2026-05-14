import { type ChangeEvent, useMemo, useState } from 'react';
import axios from 'axios';

import UploadBox from './components/UploadBox.js';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

type DocumentItem = {
  docId: string;
  filename: string;
  totalChunks: number;
  createdAt: string;
};

type Source = {
  page: number | null;
  chunk_id: number;
  confidence: number;
  score: number;
  paragraph_index: number | null;
  paragraph_text: string;
};

type ScopeInfo = {
  in_scope: boolean;
  reason: string;
  top_score: number;
  overlap: number;
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  matchedParagraph?: string;
  scope?: ScopeInfo;
};

const makeId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState('Upload a document to begin.');
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [messagesByDocument, setMessagesByDocument] = useState<Record<string, ChatMessage[]>>({});

  const activeMessages = useMemo(() => {
    if (!activeDocumentId) {
      return [] as ChatMessage[];
    }
    return messagesByDocument[activeDocumentId] ?? [];
  }, [activeDocumentId, messagesByDocument]);

  const documentReady = Boolean(activeDocumentId);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(event.target.files?.[0] ?? null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setStatusMessage('Please select a file first.');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);
    setUploading(true);
    setStatusMessage('Processing document and building vector index...');

    try {
      const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const nextDocument: DocumentItem = {
        docId: response.data.doc_id,
        filename: response.data.filename ?? selectedFile.name,
        totalChunks: response.data.total_chunks ?? 0,
        createdAt: response.data.created_at ?? new Date().toISOString(),
      };

      setDocuments((previousDocuments) => {
        const remainingDocuments = previousDocuments.filter((document) => document.docId !== nextDocument.docId);
        return [nextDocument, ...remainingDocuments];
      });
      setActiveDocumentId(nextDocument.docId);
      setStatusMessage(`${response.data.message} (${response.data.total_chunks ?? 0} chunks indexed)`);
      setSelectedFile(null);
    } catch (err) {
      console.error(err);
      setStatusMessage('Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const appendMessage = (docId: string, message: ChatMessage) => {
    setMessagesByDocument((previousMessages) => ({
      ...previousMessages,
      [docId]: [...(previousMessages[docId] ?? []), message],
    }));
  };

  const submitQuestion = async () => {
    const q = question.trim();
    if (!q || !documentReady || !activeDocumentId) {
      return;
    }

    const docId = activeDocumentId;
    const userMessage: ChatMessage = {
      id: makeId(),
      role: 'user',
      content: q,
    };

    appendMessage(docId, userMessage);
    setQuestion('');
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE_URL}/ask`, { question: q, doc_id: docId });
      const assistantMessage: ChatMessage = {
        id: makeId(),
        role: 'assistant',
        content: res.data.answer ?? 'Answer not found in document.',
        sources: res.data.sources ?? [],
        matchedParagraph: res.data.retrieved_chunks?.[0]?.paragraph_text ?? res.data.sources?.[0]?.paragraph_text ?? '',
        scope: res.data.scope ?? undefined,
      };
      appendMessage(docId, assistantMessage);
    } catch (err) {
      console.error(err);
      appendMessage(docId, {
        id: makeId(),
        role: 'assistant',
        content: 'Error generating answer.',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="chat-shell">
      <header className="chat-header">
        <h1>Document Q&A Bot</h1>
        <p className="chat-header__status">{statusMessage}</p>
      </header>

      <UploadBox
        handleFileChange={handleFileChange}
        handleUpload={handleUpload}
        uploadLabel={uploading ? 'Uploading...' : 'Upload Document'}
      />

      {documents.length > 0 ? (
        <section className="panel chat-documents">
          <div className="chat-documents__header">
            <h2>Documents</h2>
            <p>Switch between uploaded files and keep each chat transcript separate.</p>
          </div>
          <label className="chat-documents__select-label" htmlFor="document-session-select">
            Active document
          </label>
          <select
            id="document-session-select"
            className="chat-documents__select"
            value={activeDocumentId ?? ''}
            onChange={(event) => setActiveDocumentId(event.target.value)}
          >
            {documents.map((document) => (
              <option key={document.docId} value={document.docId}>
                {document.filename} ({document.totalChunks} chunks)
              </option>
            ))}
          </select>
        </section>
      ) : null}

      <section className="panel panel--upload">
        <div className="upload-form">
          <input
            type="text"
            placeholder={documentReady ? 'Ask a question about the active document...' : 'Upload a document first...'}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={!documentReady || loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                void submitQuestion();
              }
            }}
          />
          <button onClick={() => void submitQuestion()} disabled={!documentReady || loading}>
            {loading ? 'Thinking...' : 'Ask'}
          </button>
        </div>

        <section className="chat-thread" aria-live="polite">
          {activeMessages.length > 0 ? (
            activeMessages.map((message) => (
              <article key={message.id} className={`chat-bubble chat-bubble--${message.role}`}>
                <div className="chat-bubble__role">{message.role === 'user' ? 'You' : 'Assistant'}</div>
                <p className="chat-bubble__content">{message.content}</p>

                {message.scope ? (
                  <div className={`chat-scope ${message.scope.in_scope ? 'chat-scope--in' : 'chat-scope--out'}`}>
                    {message.scope.in_scope
                      ? `In scope • similarity ${Math.round(message.scope.top_score * 100)}% • overlap ${Math.round(message.scope.overlap * 100)}%`
                      : `Out of scope • ${message.scope.reason}`}
                  </div>
                ) : null}

                {message.matchedParagraph ? (
                  <div className="chat-matched-paragraph">
                    <h3>Matched paragraph</h3>
                    <p>{message.matchedParagraph}</p>
                  </div>
                ) : null}

                {message.sources && message.sources.length > 0 ? (
                  <div className="chat-sources">
                    <h3>Sources</h3>
                    {message.sources.map((source, index) => (
                      <div key={`${source.chunk_id}-${index}`} className="chat-source-card">
                        <p>
                          Page: {source.page ?? 'unknown'} • Chunk: {source.chunk_id} • Confidence: {source.confidence}%
                        </p>
                        <p>
                          Similarity: {source.score}% • Paragraph: {source.paragraph_index ?? 'unknown'}
                        </p>
                        <div className="chat-source-card__paragraph">{source.paragraph_text}</div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))
          ) : (
            <div className="empty-state">
              <p>{documentReady ? 'Ask a question to start the chat history.' : 'Upload a document to get started.'}</p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
