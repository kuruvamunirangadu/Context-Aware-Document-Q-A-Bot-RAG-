import { type ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';

import {
  API_BASE_URL,
  API_DOCS_URL,
  askQuestion,
  createSession,
  deleteSessionById,
  getApiErrorMessage,
  getBackendStatus,
  getDocument,
  getDocuments,
  getSessionMessages,
  getSessions,
  saveSessionMessage,
  uploadDocument,
  type ChatMessage,
  type ChatSession,
  type DocumentItem,
} from './api/client.js';
import UploadBox from './components/UploadBox.js';

const UNSPLASH_ACCESS_KEY = import.meta.env.VITE_UNSPLASH_ACCESS_KEY ?? 'Yf1_pqmkNoCZndjrhlo8QKIREHVwR9RZ1LbFbpdpisg';

const makeId = (): string => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const waitForDocumentReady = async (docId: string): Promise<DocumentItem> => {
  const attempts = 180;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const document = await getDocument(docId);

    if (document.status === 'ready') {
      return document;
    }

    if (document.status === 'failed') {
      throw new Error(document.error ?? 'Document processing failed');
    }

    await new Promise((resolve) => {
      window.setTimeout(resolve, 1000);
    });
  }

  throw new Error('Document processing timed out after 180 seconds');
};

const normalizeText = (value: string): string => value.toLowerCase().replace(/[_-]+/g, ' ').replace(/[^a-z0-9\s]/g, ' ');

type DocumentTheme = 'emotional' | 'technical' | 'academic' | 'neutral';
type ThemeCategory = {
  theme: DocumentTheme;
  query: string;
};

const detectDocumentTheme = (documentName: string, documentText = ''): ThemeCategory => {
  const combinedText = normalizeText(`${documentName} ${documentText}`);

  // Emotional/Calm Theme - personal, wellness, creative, feelings
  const emotionalKeywords = ['emotion', 'feeling', 'mood', 'wellness', 'mindfulness', 'creative', 'art', 'poetry', 'journal', 'diary', 'personal', 'lifestyle', 'inspiration', 'motivation', 'happiness', 'love', 'story', 'narrative', 'therapy', 'psychology', 'coaching'];
  if (emotionalKeywords.some(keyword => combinedText.includes(keyword))) {
    return { theme: 'emotional', query: 'calm serene abstract watercolor' };
  }

  // Technical/Futuristic Theme - code, tech, data, AI, engineering, systems
  const technicalKeywords = ['tech', 'data', 'ai', 'deep learning', 'machine', 'neural', 'algorithm', 'code', 'software', 'engineering', 'crypto', 'blockchain', 'cloud', 'database', 'api', 'server', 'network', 'system', 'architecture', 'framework', 'programming', 'development', 'devops', 'infrastructure'];
  if (technicalKeywords.some(keyword => combinedText.includes(keyword))) {
    return { theme: 'technical', query: 'futuristic neon technology circuit board' };
  }

  // Academic/Editorial Theme - research, papers, studies, reports, analysis
  const academicKeywords = ['research', 'paper', 'study', 'academic', 'analysis', 'report', 'thesis', 'dissertation', 'publication', 'journal', 'editorial', 'case study', 'survey', 'whitepaper', 'literature', 'science', 'experiment', 'methodology', 'findings', 'education', 'scholarly'];
  if (academicKeywords.some(keyword => combinedText.includes(keyword))) {
    return { theme: 'academic', query: 'editorial desk library books professional workspace' };
  }

  // Business/Professional but not strictly academic
  const businessKeywords = ['finance', 'budget', 'market', 'business', 'sales', 'commerce', 'investment', 'revenue', 'strategy', 'corporate', 'enterprise', 'management', 'operation', 'performance', 'analytics', 'health', 'medical', 'clinical', 'hospital', 'speech', 'voice', 'audio'];
  if (businessKeywords.some(keyword => combinedText.includes(keyword))) {
    return { theme: 'technical', query: 'professional workspace clean modern office' };
  }

  // Default neutral theme
  return { theme: 'neutral', query: 'minimal elegant workspace document' };
};

const buildBackgroundQuery = (documentName: string, documentText = ''): string => {
  const themeCategory = detectDocumentTheme(documentName, documentText);
  return themeCategory.query;
};

const fetchBackgroundImage = async (query: string): Promise<string | null> => {
  const response = await fetch(
    `https://api.unsplash.com/photos/random?query=${encodeURIComponent(query)}&client_id=${UNSPLASH_ACCESS_KEY}`,
  );

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as {
    urls?: {
      full?: string;
      regular?: string;
      raw?: string;
    };
  };

  return data.urls?.full ?? data.urls?.regular ?? data.urls?.raw ?? null;
};

export default function App() {
  const appContainerRef = useRef<HTMLDivElement | null>(null);
  const questionInputRef = useRef<HTMLInputElement | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState('Upload a document to begin.');
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [messagesByDocument, setMessagesByDocument] = useState<Record<string, ChatMessage[]>>({});
  const [backgroundImageUrl, setBackgroundImageUrl] = useState<string | null>(null);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);

  const activeMessages = useMemo(() => {
    if (!activeDocumentId) {
      return [] as ChatMessage[];
    }
    return messagesByDocument[activeDocumentId] ?? [];
  }, [activeDocumentId, messagesByDocument]);

  const activeDocument = useMemo(
    () => documents.find((document) => document.docId === activeDocumentId) ?? null,
    [activeDocumentId, documents],
  );

  const latestAssistantMessage = useMemo(
    () => [...activeMessages].reverse().find((message) => message.role === 'assistant') ?? null,
    [activeMessages],
  );

  const documentReady = Boolean(activeDocumentId);

  useEffect(() => {
    void checkBackendStatus();
    void loadDocuments();
    void loadSessions();
  }, []);

  useEffect(() => {
    if (activeSessionId) {
      void loadSessionMessages(activeSessionId);
    }
  }, [activeSessionId, sessions]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [activeMessages, loading, activeDocumentId]);

  useEffect(() => {
    if (documentReady && !loading) {
      questionInputRef.current?.focus();
    }
  }, [documentReady, loading, activeDocumentId]);

  useEffect(() => {
    if (!activeDocument) {
      setBackgroundImageUrl(null);
      return;
    }

    let cancelled = false;
    const query = buildBackgroundQuery(activeDocument.filename, latestAssistantMessage?.matchedParagraph ?? latestAssistantMessage?.content ?? '');

    const loadBackground = async () => {
      try {
        const imageUrl = await fetchBackgroundImage(query);
        if (!cancelled) {
          setBackgroundImageUrl(imageUrl);
        }
      } catch (err) {
        console.error('Failed to fetch background image', err);
        if (!cancelled) {
          setBackgroundImageUrl(null);
        }
      }
    };

    void loadBackground();

    return () => {
      cancelled = true;
    };
  }, [activeDocument?.filename, latestAssistantMessage?.content, latestAssistantMessage?.matchedParagraph]);

  useEffect(() => {
    const container = appContainerRef.current;
    if (!container) {
      return;
    }

    container.style.setProperty('--app-background-image', backgroundImageUrl ? `url('${backgroundImageUrl}')` : 'none');
  }, [backgroundImageUrl]);

  const loadDocuments = async () => {
    try {
      const { documents: nextDocuments, activeDocumentId: serverActiveId } = await getDocuments();

      setDocuments(nextDocuments);

      if (serverActiveId && nextDocuments.some((doc: DocumentItem) => doc.docId === serverActiveId)) {
        setActiveDocumentId(serverActiveId);
      } else if (nextDocuments.length > 0) {
        setActiveDocumentId(nextDocuments[0].docId);
      }
    } catch (err) {
      console.error('Failed to load documents', err);
      setStatusMessage(`Backend is not reachable at ${API_BASE_URL}. Check the Render service deploy.`);
    }
  };

  const checkBackendStatus = async () => {
    try {
      await getBackendStatus();
    } catch (err) {
      console.error('Backend health check failed', err);
      setStatusMessage(`Backend is not reachable at ${API_BASE_URL}. Check the Render service deploy.`);
    }
  };

  const loadSessions = async () => {
    try {
      setSessions(await getSessions());
    } catch (err) {
      console.error('Failed to load sessions', err);
    }
  };

  const loadSessionMessages = async (sessionId: string) => {
    try {
      const messages = await getSessionMessages(sessionId);
      const session = sessions.find((entry) => entry.session_id === sessionId);
      if (!session) {
        return;
      }

      setActiveDocumentId(session.document_id);
      setMessagesByDocument((prev) => ({
        ...prev,
        [session.document_id]: messages,
      }));
    } catch (err) {
      console.error('Failed to load session messages', err);
    }
  };

  const createNewSession = async (docId: string, docName: string) => {
    const sessionId = makeId();
    try {
      await createSession(sessionId, docId, docName);
      setActiveSessionId(sessionId);
      await loadSessions();
    } catch (err) {
      console.error('Failed to create session', err);
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      await deleteSessionById(sessionId);
      await loadSessions();
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
    } catch (err) {
      console.error('Failed to delete session', err);
    }
  };

  const appendMessage = (docId: string, message: ChatMessage) => {
    setMessagesByDocument((prev) => ({
      ...prev,
      [docId]: [...(prev[docId] ?? []), message],
    }));
  };

  const persistMessage = async (sessionId: string, message: ChatMessage) => {
    try {
      await saveSessionMessage(sessionId, message);
    } catch (err) {
      console.error('Failed to save message', err);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(event.target.files?.[0] ?? null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setStatusMessage('Please select a file first.');
      return;
    }

    setUploading(true);
    setStatusMessage(
      selectedFile.name.toLowerCase().endsWith('.pdf')
        ? 'Extracting text from PDF before uploading to backend...'
        : 'Processing document and building vector index...',
    );

    try {
      const { document: acceptedDocument, message } = await uploadDocument(selectedFile);

      setDocuments((prev) => [acceptedDocument, ...prev.filter((doc) => doc.docId !== acceptedDocument.docId)]);
      setActiveDocumentId(acceptedDocument.docId);
      setStatusMessage(`${message} Checking indexing status...`);

      const nextDocument = await waitForDocumentReady(acceptedDocument.docId);

      setDocuments((prev) => [nextDocument, ...prev.filter((doc) => doc.docId !== nextDocument.docId)]);
      setActiveDocumentId(nextDocument.docId);
      setMessagesByDocument((prev) => ({ ...prev, [nextDocument.docId]: [] }));
      setStatusMessage(`${message} (${nextDocument.totalChunks} chunks indexed)`);
      setSelectedFile(null);

      await createNewSession(nextDocument.docId, nextDocument.filename);
    } catch (err) {
      console.error(err);
      setStatusMessage(`Upload failed: ${getApiErrorMessage(err)}. Check Render logs for upload_* events.`);
    } finally {
      setUploading(false);
    }
  };

  const submitQuestion = async () => {
    const q = question.trim();
    if (!q || !activeDocumentId || loading) {
      return;
    }

    const userMessage: ChatMessage = {
      id: makeId(),
      role: 'user',
      content: q,
    };

    appendMessage(activeDocumentId, userMessage);
    setQuestion('');
    setLoading(true);

    if (activeSessionId) {
      void persistMessage(activeSessionId, userMessage);
    }

    try {
      const answer = await askQuestion(q, activeDocumentId);
      const assistantMessage: ChatMessage = {
        id: makeId(),
        role: 'assistant',
        content: answer.answer,
        sources: answer.sources,
        matchedParagraph: answer.matchedParagraph,
        scope: answer.scope,
      };

      appendMessage(activeDocumentId, assistantMessage);
      if (activeSessionId) {
        void persistMessage(activeSessionId, assistantMessage);
      }
    } catch (err) {
      console.error(err);
      appendMessage(activeDocumentId, {
        id: makeId(),
        role: 'assistant',
        content: 'Error generating answer.',
      });
    } finally {
      setLoading(false);
      questionInputRef.current?.focus();
    }
  };

  return (
    <div className="app-container" ref={appContainerRef}>
      <div className="app-background" aria-hidden="true" />
      <aside className={`chat-sidebar ${showSidebar ? 'chat-sidebar--visible' : 'chat-sidebar--hidden'}`}>
        <div className="chat-sidebar__header">
          <h2>Chat History</h2>
          <button className="chat-sidebar__toggle" onClick={() => setShowSidebar((prev) => !prev)} aria-label="Toggle sidebar">
            ☰
          </button>
        </div>

        <div className="chat-sidebar__sessions">
          {sessions.length > 0 ? (
            sessions.map((session) => (
              <div key={session.session_id} className={`chat-session-item ${activeSessionId === session.session_id ? 'chat-session-item--active' : ''}`}>
                <button
                  className="chat-session-item__button"
                  onClick={() => setActiveSessionId(session.session_id)}
                  title={session.title}
                >
                  <span className="chat-session-item__title">{session.title}</span>
                  <span className="chat-session-item__doc">{session.document_name}</span>
                </button>
                <button
                  className="chat-session-item__delete"
                  onClick={() => void deleteSession(session.session_id)}
                  aria-label="Delete session"
                >
                  x
                </button>
              </div>
            ))
          ) : (
            <p className="chat-sidebar__empty">No chat history yet. Upload a document to start.</p>
          )}
        </div>
      </aside>

      <main className="chat-shell">
        <header className="chat-header">
          <button className="chat-header__menu-button" onClick={() => setShowSidebar((prev) => !prev)} aria-label="Toggle sidebar">
            ☰
          </button>
          <div>
            <h1>Document Q&A Bot</h1>
            <p className="chat-header__status">{statusMessage}</p>
          </div>
          <div className="chat-header__links">
            <a className="chat-header__link" href={API_BASE_URL} target="_blank" rel="noreferrer">
              Backend API
            </a>
            <a className="chat-header__link" href={API_DOCS_URL} target="_blank" rel="noreferrer">
              API Docs
            </a>
          </div>
        </header>

        {activeDocument ? (
          <section className="theme-banner" aria-label="Document theme preview">
            <div className="theme-banner__image" aria-hidden="true" />
            <div className="theme-banner__content">
              <p className="theme-banner__label">Document mood</p>
              <h2>{activeDocument.filename}</h2>
              <p>
                Visual theme is generated from the document topic and recent answer context. If the image feels off, I can tune
                the query.
              </p>
            </div>
          </section>
        ) : null}

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
              ref={questionInputRef}
              type="text"
              placeholder={documentReady ? 'Ask a question about the active document...' : 'Upload a document first...'}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled={!documentReady || loading}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
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
                            Similarity: {typeof source.score === 'number' ? (source.score * 100).toFixed(2) : source.score}% • Paragraph:{' '}
                            {source.paragraph_index ?? 'unknown'}
                          </p>
                          <div className="chat-source-card__paragraph">{source.paragraph_text}</div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))
            ) : (
              <div className="chat-thread__empty">
                <p>Upload a document to get started.</p>
              </div>
            )}
            <div ref={threadEndRef} />
          </section>
        </section>
      </main>
    </div>
  );
}
