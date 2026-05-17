import { useState, useEffect, useCallback, useRef } from 'react';
import { ArrowLeft, RefreshCw, MessageSquare, X, Send, CheckCircle, AlertCircle, Loader, Download } from 'lucide-react';
import Sidebar from './components/Sidebar';
import UploadZone from './components/UploadZone';
import DocumentCard from './components/DocumentCard';
import RiskDashboard from './components/RiskDashboard';
import ClauseInspector from './components/ClauseInspector';
import LiveAnalysisProgress from './components/LiveAnalysisProgress';
import { listDocuments, getAnalysis, getDocumentStatus, deleteDocument, updateSettings, sendChatMessage, getSettings } from './api';
import type { DocumentListItem, AnalysisResponse, ChatMessage, ServerSettings } from './api';
import './App.css';
import { downloadReport } from './utils/reportExport';

function App() {
  const [view, setView] = useState<'dashboard' | 'upload' | 'analysis' | 'settings'>('dashboard');
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [failureMessage, setFailureMessage] = useState<string | null>(null);

  // Server settings state
  const [serverSettings, setServerSettings] = useState<ServerSettings | null>(null);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini');

  const fetchServerSettings = useCallback(async (retries = 3) => {
    for (let i = 0; i < retries; i++) {
      try {
        const s = await getSettings();
        setServerSettings(s);
        setSelectedProvider(s.provider || 'gemini');
        return;
      } catch {
        if (i < retries - 1) {
          // Render free tier cold-starts can take 20-30s — wait before retry
          await new Promise(r => setTimeout(r, 8000));
        }
      }
    }
    // After all retries, set an offline marker so UI shows useful message
    setServerSettings({ provider: '', model: '', configured: false, gemini_key_set: false, openrouter_key_set: false } as any);
  }, []);

  useEffect(() => { fetchServerSettings(); }, [fetchServerSettings]);

  // Chat State
  const [chatOpen, setChatOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, chatOpen]);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !selectedDocId) return;
    
    const newMessages: ChatMessage[] = [...chatHistory, { role: 'user', content: chatInput }];
    setChatHistory(newMessages);
    setChatInput('');
    setChatLoading(true);
    
    try {
      const res = await sendChatMessage(selectedDocId, newMessages);
      setChatHistory([...newMessages, { role: 'ai', content: res.response }]);
    } catch (err: any) {
      alert('Chat error: ' + err.message);
      setChatHistory(newMessages.slice(0, -1)); // Revert on fail
    } finally {
      setChatLoading(false);
    }
  };

  const fetchDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const loadAnalysis = useCallback(async (docId: string, options?: { keepView?: boolean }) => {
    setLoading(true);
    setSelectedDocId(docId);
    setAnalysisError(null);
    setFailureMessage(null);
    if (!options?.keepView) {
      setView('analysis');
    }
    try {
      const data = await getAnalysis(docId);
      setAnalysis(data);
      if (data.status === 'completed' || data.status === 'failed') {
        setPolling(null);
        // If failed, fetch the real error message from the status endpoint
        if (data.status === 'failed') {
          try {
            const status = await getDocumentStatus(docId);
            setFailureMessage(status.error_message || 'Analysis failed — check your API key and quota.');
          } catch {
            setFailureMessage('Analysis failed. Check your API key in Settings.');
          }
        }
        await fetchDocuments();
      } else {
        setPolling(docId);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load analysis';
      setAnalysisError(message);
      console.error('Failed to load analysis:', err);
    } finally {
      setLoading(false);
    }
  }, [fetchDocuments]);

  // Fallback poll if SSE disconnects
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      try {
        const status = await getDocumentStatus(polling);
        if (status.error_message) setFailureMessage(status.error_message);
        if (status.status === 'completed' || status.status === 'failed') {
          setPolling(null);
          await loadAnalysis(polling, { keepView: true });
        }
      } catch (err) {
        console.error('Status poll failed:', err);
      }
    }, 8000);
    return () => clearInterval(interval);
  }, [polling, loadAnalysis]);

  const handleAnalysisComplete = useCallback(async () => {
    const docId = polling;
    if (!docId) return;
    await new Promise((r) => setTimeout(r, 400));
    setPolling(null);
    await loadAnalysis(docId, { keepView: true });
  }, [polling, loadAnalysis]);

  const handleUploadComplete = (docId: string) => {
    setPolling(docId);
    fetchDocuments();
    loadAnalysis(docId);
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document and its analysis?')) return;
    try {
      await deleteDocument(docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
      if (selectedDocId === docId) { setView('dashboard'); setAnalysis(null); }
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  return (
    <div className="app-layout">
      <Sidebar currentView={view} onNavigate={(v) => setView(v as any)} documentCount={documents.length} />

      <main className="main-content">
        {/* Dashboard View */}
        {view === 'dashboard' && (
          <div className="animate-fade-in">
            <div className="page-header">
              <div>
                <h1>Contract <span className="gradient-text">Intelligence</span></h1>
                <p>Upload contracts to identify risks, understand implications, and get negotiation guidance.</p>
              </div>
              <div className="header-actions">
                <button className="btn-secondary" onClick={fetchDocuments} aria-label="Refresh document list"><RefreshCw size={16} aria-hidden="true" /> Refresh</button>
                <button className="btn-primary" onClick={() => setView('upload')} aria-label="Start new contract analysis">+ New Analysis</button>
              </div>
            </div>

            {documents.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📄</div>
                <h3>No documents yet</h3>
                <p>Upload your first contract to get started with AI-powered risk analysis.</p>
                <button className="btn-primary" onClick={() => setView('upload')}>Upload Contract</button>
              </div>
            ) : (
              <div className="documents-grid">
                {documents.map(doc => (
                  <DocumentCard key={doc.id} doc={doc} onSelect={loadAnalysis} onDelete={handleDelete} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Upload View */}
        {view === 'upload' && (
          <div className="animate-fade-in">
            <div className="page-header">
              <div>
                <h1>Upload <span className="gradient-text">Contract</span></h1>
                <p>Supported formats: PDF, DOCX, TXT, JPG/PNG. Max 50MB.</p>
              </div>
            </div>
            <UploadZone onUploadComplete={handleUploadComplete} />
          </div>
        )}

        {/* Analysis View */}
        {view === 'analysis' && (
          <div className="animate-fade-in">
            <div className="page-header">
              <div className="back-header">
                <button
                  className="btn-secondary back-btn"
                  onClick={() => setView('dashboard')}
                  aria-label="Back to dashboard"
                >
                  <ArrowLeft size={16} aria-hidden="true" /> Back
                </button>
                <div>
                  <h2>{analysis?.filename || 'Loading...'}</h2>
                  {analysis?.risk_summary && (
                    <p aria-live="polite">Analysed {analysis.risk_summary.total_clauses} clauses in {analysis.risk_summary.processing_time.toFixed(1)}s</p>
                  )}
                </div>
              </div>
              {analysis?.status === 'completed' && analysis.clauses.length > 0 && (
                <button
                  className="btn-secondary"
                  onClick={() => downloadReport(analysis)}
                  aria-label="Download risk report as text file"
                  style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                >
                  <Download size={16} aria-hidden="true" /> Export Report
                </button>
              )}
            </div>

            {analysisError && (
              <div className="analysis-error" role="alert" aria-live="assertive">{analysisError}</div>
            )}

            {analysis?.status === 'failed' ? (
              (() => {
                const msg = failureMessage || '';
                const isQuota = msg.toLowerCase().includes('quota') || msg.includes('429') || msg.includes('RESOURCE_EXHAUSTED');
                const isAuth  = msg.toLowerCase().includes('invalid') || msg.includes('401') || msg.includes('403') || msg.toLowerCase().includes('api key');
                const isNoText = msg.toLowerCase().includes('no text') || msg.toLowerCase().includes('extracted');
                return (
                  <div className="empty-state" style={{ marginTop: 24 }} role="alert">
                    <div className="empty-icon" aria-hidden="true">
                      {isQuota ? '⏱️' : isAuth ? '🔑' : '⚠️'}
                    </div>
                    <h3>
                      {isQuota ? 'API Quota Exceeded'
                        : isAuth ? 'Invalid API Key'
                        : isNoText ? 'No Text Extracted'
                        : 'Analysis Failed'}
                    </h3>
                    <p style={{ maxWidth: 520, margin: '0 auto 16px', lineHeight: 1.6 }}>
                      {msg || 'An unexpected error occurred. Please try again.'}
                    </p>
                    {isQuota && (
                      <p style={{ fontSize: 13, opacity: 0.7, marginBottom: 16 }}>
                        Free tier: ~15 req/min on gemini-2.0-flash. Wait 60s or switch to OpenRouter in Settings.
                      </p>
                    )}
                    <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                      {(isAuth || isQuota) && (
                        <button className="btn-secondary" onClick={() => setView('settings')}>Open Settings</button>
                      )}
                      <button className="btn-primary" onClick={() => setView('upload')}>Try Again</button>
                    </div>
                  </div>
                );
              })()
            ) : loading || !analysis || analysis.status !== 'completed' ? (
              polling ? (
                <LiveAnalysisProgress documentId={polling} onComplete={handleAnalysisComplete} />
              ) : (
                <div className="empty-state"><p>Loading…</p></div>
              )
            ) : analysis.clauses.length === 0 ? (
              <div className="empty-state" style={{ marginTop: 24 }}>
                <div className="empty-icon">📋</div>
                <h3>No clauses extracted</h3>
                <p>The document was processed but no clauses were found. Try a longer contract or check your Gemini API key and quota.</p>
              </div>
            ) : (
              <>
                {analysis.risk_summary && analysis.risk_analyses.length > 0 && (
                  <RiskDashboard summary={analysis.risk_summary} risks={analysis.risk_analyses} />
                )}
                <div style={{ marginTop: 24 }}>
                  <ClauseInspector
                    clauses={analysis.clauses}
                    risks={analysis.risk_analyses}
                    implications={analysis.implications}
                    ambiguities={analysis.ambiguities}
                    marketBenchmarks={analysis.market_benchmarks}
                    privacyCompliance={analysis.privacy_compliance}
                    relationships={analysis.relationships}
                    negotiationGuidance={analysis.negotiation_guidance}
                  />
                </div>

                {/* AI Lawyer Chat Floating Action Button */}
                <button 
                  className="btn-primary" 
                  style={{ position: 'fixed', bottom: 32, right: 32, borderRadius: '50%', width: 64, height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 16px rgba(0,0,0,0.3)', zIndex: 1000 }}
                  onClick={() => setChatOpen(true)}
                >
                  <MessageSquare size={28} />
                </button>

                {/* Floating Chat Window */}
                {chatOpen && (
                  <div style={{ position: 'fixed', bottom: 32, right: 32, width: 400, height: 500, background: 'var(--bg-secondary)', borderRadius: 12, boxShadow: '0 12px 32px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', zIndex: 1001, border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                    {/* Chat Header */}
                    <div style={{ padding: '16px', background: 'var(--card-bg)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--primary-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 'bold' }}>AI</div>
                        <div>
                          <h3 style={{ margin: 0, fontSize: '1rem' }}>AI Lawyer</h3>
                          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Negotiation & Modification Advice</p>
                        </div>
                      </div>
                      <button onClick={() => setChatOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}><X size={20} /></button>
                    </div>

                    {/* Chat Messages */}
                    <div style={{ flex: 1, padding: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {chatHistory.length === 0 && (
                        <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '50%' }}>
                          <MessageSquare size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
                          <p>Ask me how to negotiate or modify this contract!</p>
                        </div>
                      )}
                      {chatHistory.map((msg, idx) => (
                        <div key={idx} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%', background: msg.role === 'user' ? 'var(--primary-color)' : 'var(--card-bg)', color: msg.role === 'user' ? '#fff' : 'var(--text-primary)', padding: '10px 14px', borderRadius: 12, border: msg.role === 'ai' ? '1px solid var(--border-color)' : 'none' }}>
                          <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.4' }}>{msg.content}</p>
                        </div>
                      ))}
                      {chatLoading && (
                        <div style={{ alignSelf: 'flex-start', background: 'var(--card-bg)', color: 'var(--text-secondary)', padding: '10px 14px', borderRadius: 12, border: '1px solid var(--border-color)' }}>
                          <p style={{ margin: 0, fontSize: '0.9rem' }}>Typing...</p>
                        </div>
                      )}
                      <div ref={messagesEndRef} />
                    </div>

                    {/* Chat Input */}
                    <form onSubmit={handleChatSubmit} style={{ padding: 16, background: 'var(--card-bg)', borderTop: '1px solid var(--border-color)', display: 'flex', gap: 8 }}>
                      <input 
                        type="text" 
                        value={chatInput}
                        onChange={e => setChatInput(e.target.value)}
                        placeholder="Type your message..."
                        disabled={chatLoading}
                        style={{ flex: 1, padding: '10px 14px', borderRadius: 20, border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', outline: 'none' }}
                      />
                      <button type="submit" disabled={chatLoading || !chatInput.trim()} style={{ background: 'var(--primary-color)', color: '#fff', border: 'none', borderRadius: '50%', width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', opacity: (chatLoading || !chatInput.trim()) ? 0.5 : 1 }}>
                        <Send size={16} />
                      </button>
                    </form>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Settings View */}
        {view === 'settings' && (
          <div className="animate-fade-in">
            <div className="page-header">
              <div>
                <h1>App <span className="gradient-text">Settings</span></h1>
                <p>Configure your AI provider and API key. Changes take effect immediately — no restart needed.</p>
              </div>
              <button className="btn-secondary" onClick={() => fetchServerSettings()}>
                <RefreshCw size={16} /> Refresh Status
              </button>
            </div>

            {/* Status Card */}
            <div className="card" style={{ maxWidth: 640, margin: '0 auto 1.5rem', padding: '1.25rem 1.5rem', display: 'flex', alignItems: 'center', gap: 12 }}>
              {serverSettings === null ? (
                <><Loader size={18} className="spin" /><span style={{ color: 'var(--text-secondary)' }}>Connecting to backend… (may take ~30s on first load)</span></>
              ) : serverSettings.configured ? (
                <><CheckCircle size={20} color="#22c55e" />
                  <div>
                    <strong style={{ color: '#22c55e' }}>API Configured ✓</strong>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      Provider: <strong>{serverSettings.provider}</strong> · Model: <strong>{serverSettings.model}</strong>
                    </p>
                  </div>
                </>
              ) : (
                <><AlertCircle size={20} color="#f97316" />
                  <div>
                    <strong style={{ color: '#f97316' }}>API Key Required</strong>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Enter your API key below to enable contract analysis.</p>
                  </div>
                </>
              )}
            </div>

            {/* Settings Form */}
            <div className="card" style={{ maxWidth: 640, margin: '0 auto', padding: '2rem' }}>
              <form onSubmit={async (e) => {
                e.preventDefault();
                const fd = new FormData(e.currentTarget);
                const api_key = (fd.get('api_key') as string).trim();
                const provider = selectedProvider;
                if (!api_key) { setSettingsMsg({ type: 'error', text: 'Please enter your API key.' }); return; }
                setSettingsSaving(true);
                setSettingsMsg(null);
                try {
                  await updateSettings({ api_key, provider });
                  await fetchServerSettings();
                  setSettingsMsg({ type: 'success', text: 'Settings saved! Your API key is now active.' });
                  (e.target as HTMLFormElement).reset();
                } catch (err: any) {
                  setSettingsMsg({ type: 'error', text: err.message || 'Failed to save settings.' });
                } finally {
                  setSettingsSaving(false);
                }
              }}>
                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, fontSize: '0.9rem' }}>LLM Provider</label>
                  <div style={{ display: 'flex', gap: 12 }}>
                    {[{ id: 'gemini', label: 'Google Gemini', hint: 'Get key at aistudio.google.com' },
                      { id: 'openrouter', label: 'OpenRouter', hint: 'Get key at openrouter.ai/keys' }].map(p => (
                      <label key={p.id} style={{ flex: 1, padding: '1rem', borderRadius: 10, border: `2px solid ${selectedProvider === p.id ? 'var(--primary-color)' : 'var(--border-color)'}`, cursor: 'pointer', background: selectedProvider === p.id ? 'rgba(99,102,241,0.08)' : 'transparent', transition: 'all 0.2s' }}>
                        <input type="radio" name="provider_radio" value={p.id} checked={selectedProvider === p.id} onChange={() => setSelectedProvider(p.id)} style={{ display: 'none' }} />
                        <strong style={{ display: 'block', marginBottom: 4 }}>{p.label}</strong>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{p.hint}</span>
                        {serverSettings && ((p.id === 'gemini' && serverSettings.gemini_key_set) || (p.id === 'openrouter' && serverSettings.openrouter_key_set)) && (
                          <span style={{ display: 'block', marginTop: 4, fontSize: '0.78rem', color: '#22c55e' }}>✓ Key saved</span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600, fontSize: '0.9rem' }}>API Key</label>
                  <input
                    type="password"
                    name="api_key"
                    placeholder={selectedProvider === 'gemini' ? 'AIzaSy...' : 'sk-or-v1-...'}
                    autoComplete="off"
                    required
                    style={{ width: '100%', padding: '0.85rem 1rem', borderRadius: 8, border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '1rem', boxSizing: 'border-box' }}
                  />
                  <p style={{ margin: '0.4rem 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Your key is stored only on the backend and never sent to the browser.
                  </p>
                </div>

                {settingsMsg && (
                  <div style={{ padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem', background: settingsMsg.type === 'success' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)', border: `1px solid ${settingsMsg.type === 'success' ? '#22c55e44' : '#ef444444'}`, color: settingsMsg.type === 'success' ? '#22c55e' : '#ef4444', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {settingsMsg.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                    {settingsMsg.text}
                  </div>
                )}

                <button type="submit" className="btn-primary" style={{ width: '100%', padding: '0.85rem', fontSize: '1rem' }} disabled={settingsSaving}>
                  {settingsSaving ? 'Saving...' : 'Save Settings'}
                </button>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
