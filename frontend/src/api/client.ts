import axios from 'axios';

const RENDER_BACKEND_URL = 'https://context-aware-document-q-a-bot-rag-1.onrender.com';
const API_TIMEOUT_MS = 30000;
const UPLOAD_TIMEOUT_MS = 180000;

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? RENDER_BACKEND_URL).replace(/\/$/, '');
export const API_DOCS_URL = `${API_BASE_URL}/docs`;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
});

export type DocumentItem = {
  docId: string;
  filename: string;
  totalChunks: number;
  createdAt: string;
  status: 'processing' | 'ready' | 'failed';
  error?: string | null;
};

export type Source = {
  page: number | null;
  chunk_id: number;
  confidence: number;
  score: number;
  paragraph_index: number | null;
  paragraph_text: string;
};

export type ScopeInfo = {
  in_scope: boolean;
  reason: string;
  top_score: number;
  overlap: number;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  matchedParagraph?: string;
  scope?: ScopeInfo;
};

export type ChatSession = {
  session_id: string;
  document_id: string;
  document_name: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type BackendDocument = {
  doc_id?: string;
  docId?: string;
  filename?: string;
  total_chunks?: number;
  totalChunks?: number;
  created_at?: string;
  createdAt?: string;
  status?: string;
  error?: string | null;
};

export type DocumentsResult = {
  documents: DocumentItem[];
  activeDocumentId: string | null;
};

export type UploadDocumentResult = {
  message: string;
  document: DocumentItem;
};

export type AskQuestionResult = {
  answer: string;
  sources: Source[];
  matchedParagraph: string;
  scope?: ScopeInfo;
};

export const getApiErrorMessage = (error: unknown): string => {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : 'Unexpected error';
  }

  const detail = error.response?.data?.detail ?? error.response?.data?.message;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (error.code === 'ECONNABORTED') {
    return `Request timed out after ${Math.round((error.config?.timeout ?? API_TIMEOUT_MS) / 1000)} seconds`;
  }

  return error.message || 'Request failed';
};

const toDocument = (raw: unknown): DocumentItem | null => {
  const doc = raw as BackendDocument;
  const docId = String(doc.doc_id ?? doc.docId ?? '');

  if (!docId) {
    return null;
  }

  return {
    docId,
    filename: String(doc.filename ?? 'Untitled'),
    totalChunks: Number(doc.total_chunks ?? doc.totalChunks ?? 0),
    createdAt: String(doc.created_at ?? doc.createdAt ?? new Date().toISOString()),
    status: doc.status === 'processing' || doc.status === 'failed' ? doc.status : 'ready',
    error: typeof doc.error === 'string' ? doc.error : null,
  };
};

export const getDocuments = async (): Promise<DocumentsResult> => {
  const response = await apiClient.get('/documents');
  const rawDocuments: unknown[] = Array.isArray(response.data?.documents) ? response.data.documents : [];

  return {
    documents: rawDocuments
      .map((raw) => toDocument(raw))
      .filter((value: DocumentItem | null): value is DocumentItem => value !== null),
    activeDocumentId: typeof response.data?.active_document_id === 'string' ? response.data.active_document_id : null,
  };
};

export const getBackendStatus = async (): Promise<string> => {
  const response = await apiClient.get('/');
  return String(response.data?.message ?? 'Backend is reachable');
};

export const getDocument = async (docId: string): Promise<DocumentItem> => {
  const response = await apiClient.get(`/documents/${docId}`);
  const document = toDocument(response.data);

  if (!document) {
    throw new Error('Document was not found in backend response');
  }

  return document;
};

export const uploadDocument = async (file: File): Promise<UploadDocumentResult> => {
  const formData = new FormData();
  formData.append('file', file);

  console.info('Uploading document to backend', {
    apiBaseUrl: API_BASE_URL,
    endpoint: '/upload',
    filename: file.name,
    size: file.size,
  });

  const response = await apiClient.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: UPLOAD_TIMEOUT_MS,
  });

  const document: DocumentItem = {
    docId: String(response.data?.doc_id),
    filename: String(response.data?.filename ?? file.name),
    totalChunks: Number(response.data?.total_chunks ?? 0),
    createdAt: new Date().toISOString(),
    status: response.data?.status === 'processing' ? 'processing' : 'ready',
    error: null,
  };

  return {
    document,
    message: String(response.data?.message ?? 'Document processed'),
  };
};

export const askQuestion = async (question: string, docId: string): Promise<AskQuestionResult> => {
  const response = await apiClient.post('/ask', { question, doc_id: docId });

  return {
    answer: String(response.data?.answer ?? 'Answer not found in document.'),
    sources: (response.data?.sources ?? []) as Source[],
    matchedParagraph: String(response.data?.retrieved_chunks?.[0]?.paragraph_text ?? response.data?.sources?.[0]?.paragraph_text ?? ''),
    scope: response.data?.scope as ScopeInfo | undefined,
  };
};

export const getSessions = async (): Promise<ChatSession[]> => {
  const response = await apiClient.get('/sessions');
  return Array.isArray(response.data?.sessions) ? (response.data.sessions as ChatSession[]) : [];
};

export const getSessionMessages = async (sessionId: string): Promise<ChatMessage[]> => {
  const response = await apiClient.get(`/sessions/${sessionId}/messages`);
  return (Array.isArray(response.data?.messages) ? response.data.messages : []) as ChatMessage[];
};

export const createSession = async (sessionId: string, docId: string, docName: string): Promise<void> => {
  await apiClient.post('/sessions/create', {
    session_id: sessionId,
    doc_id: docId,
    doc_name: docName,
  });
};

export const deleteSessionById = async (sessionId: string): Promise<void> => {
  await apiClient.delete(`/sessions/${sessionId}`);
};

export const saveSessionMessage = async (sessionId: string, message: ChatMessage): Promise<void> => {
  await apiClient.post(`/sessions/${sessionId}/messages`, {
    session_id: sessionId,
    message_id: message.id,
    role: message.role,
    content: message.content,
    sources: message.sources,
    matched_paragraph: message.matchedParagraph,
    scope: message.scope,
  });
};
