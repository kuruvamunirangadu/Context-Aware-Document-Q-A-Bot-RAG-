import { type ChangeEvent, useState } from 'react';
import axios from 'axios';

import UploadBox from './components/UploadBox.js';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

type Source = { page: number | null; chunk_id: number; confidence: number };

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState('Upload a document to begin.');
  const [uploading, setUploading] = useState(false);
  const [documentReady, setDocumentReady] = useState(false);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[] | null>(null);

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
      setDocumentReady(true);
      setStatusMessage(`${response.data.message} (${response.data.total_chunks ?? 0} chunks indexed)`);
      setAnswer(null);
      setSources(null);
    } catch (err) {
      console.error(err);
      setDocumentReady(false);
      setStatusMessage('Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  const submitQuestion = async () => {
    const q = question.trim();
    if (!q || !documentReady) return;
    setLoading(true);
    setAnswer(null);
    setSources(null);

    try {
      const res = await axios.post(`${API_BASE_URL}/ask`, { question: q });
      setAnswer(res.data.answer ?? 'Answer not found in document.');
      setSources(res.data.sources ?? null);
    } catch (err) {
      console.error(err);
      setAnswer('Error generating answer.');
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

      <UploadBox handleFileChange={handleFileChange} handleUpload={handleUpload} uploadLabel={uploading ? 'Uploading...' : 'Upload Document'} />

      <section className="panel panel--upload">
        <div className="upload-form">
          <input
            type="text"
            placeholder={documentReady ? 'Ask a question about your document...' : 'Upload a document first...'}
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

        {answer ? (
          <div className="panel" style={{ marginTop: 12 }}>
            <h2>Answer</h2>
            <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>

            {sources && sources.length > 0 ? (
              <div className="sources" style={{ marginTop: 12 }}>
                <h3>Sources</h3>
                {sources.map((s, i) => (
                  <div key={`${s.chunk_id}-${i}`} className="source-card">
                    <div className="source-card__meta">Page: {s.page ?? 'unknown'} • Chunk: {s.chunk_id} • Confidence: {s.confidence}%</div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="empty-state">
            <p>{documentReady ? 'Type a question and press Ask.' : 'Upload a document to get started.'}</p>
          </div>
        )}
      </section>
    </main>
  );
}