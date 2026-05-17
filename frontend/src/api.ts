const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

function formatApiError(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'object' && item && 'msg' in item ? String((item as { msg: string }).msg) : String(item)))
      .join('; ');
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: string }).message);
  }
  return fallback;
}

async function parseJsonResponse<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(formatApiError((err as { detail?: unknown }).detail, fallback));
  }
  return res.json();
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  message: string;
}

export interface DocumentListItem {
  id: string;
  filename: string;
  upload_date: string;
  file_type: string;
  status: string;
  overall_risk_score: number;
  overall_severity: string;
  clause_count: number;
  page_count: number;
}

export interface FinancialExposure {
  amount: number | null;
  currency: string;
  scenario: string;
}

export interface Recommendation {
  action: string;
  suggested_language: string | null;
  priority: number;
}

export interface ContributingFactor {
  factor: string;
  contribution: number;
  explanation: string;
}

export interface UserImpact {
  financial: string;
  operational: string;
  legal: string;
}

export interface ExtractedClause {
  id: string;
  type: string;
  section_reference: string;
  text: string;
  key_terms: string[];
  parties_affected: string[];
  ambiguities: string[];
  confidence_score: number;
}

export interface RiskAnalysis {
  clause_id: string;
  primary_category: string;
  subcategory: string;
  severity_score: number;
  severity_level: string;
  severity_reasoning: string;
  likelihood_percentage: number;
  likelihood_reasoning: string;
  parties_affected: string[];
  financial_exposure: FinancialExposure | null;
  legal_exposure: string;
  market_comparison: string;
  ambiguities: string[];
  recommendations: Recommendation[];
  contributing_factors: ContributingFactor[];
  user_impact: UserImpact | null;
}

export interface Scenario {
  trigger: string;
  financial_impact: FinancialExposure | null;
  legal_implications: string;
  timeline: string;
  mitigations: string[];
}

export interface ImplicationsResult {
  clause_id: string;
  scenarios: Scenario[];
}

export interface AmbiguityResult {
  clause_id: string;
  ambiguities: { term: string; issue: string; interpretations: string[]; exploitation_risk: string }[];
  contradictions: { clause_a: string; clause_b: string; nature: string }[];
  clarification_recommendations: string[];
}

export interface RiskSummary {
  overall_score: number;
  severity_level: string;
  signing_recommendation: string;
  total_clauses: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  none_count: number;
  key_findings: string[];
  risk_by_category: Record<string, number>;
  processing_time: number;
}

export interface MarketBenchmarkResult {
  clause_id: string;
  prevalence_percentage: number;
  deviation_level: string;
  market_norm_description: string;
  fair_alternative: string;
}

export interface PrivacyComplianceResult {
  clause_id: string;
  gdpr_compliant: boolean;
  ccpa_compliant: boolean;
  violations: string[];
  required_consents: string[];
}

export interface RelationshipMappingResult {
  clause_id: string;
  depends_on: string[];
  conflicts_with: string[];
  compound_risk_description: string;
}

export interface NegotiationGuidanceResult {
  clause_id: string;
  leverage_points: string[];
  trade_off_options: string[];
  walk_away_threshold: string;
  suggested_redline: string;
}

export interface AnalysisResponse {
  document_id: string;
  filename: string;
  status: string;
  risk_summary: RiskSummary | null;
  clauses: ExtractedClause[];
  risk_analyses: RiskAnalysis[];
  implications: ImplicationsResult[];
  ambiguities: AmbiguityResult[];
  market_benchmarks: MarketBenchmarkResult[];
  privacy_compliance: PrivacyComplianceResult[];
  relationships: RelationshipMappingResult[];
  negotiation_guidance: NegotiationGuidanceResult[];
}

export interface DocumentStatusResponse {
  document_id: string;
  status: string;
  error_message?: string | null;
  overall_risk_score?: number;
  overall_severity?: string;
  progress_percent?: number;
  progress_message?: string;
  progress_step?: string;
}

export interface ProgressEvent {
  type: string;
  document_id: string;
  status: string;
  message: string;
  percent: number;
  step?: string;
  detail?: string;
  timestamp?: string;
}

/** Subscribe to real-time SSE progress for a document. Returns unsubscribe function. */
export function subscribeDocumentProgress(
  documentId: string,
  onEvent: (event: ProgressEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const url = `${API_BASE}/documents/${documentId}/events`;
  const es = new EventSource(url);

  es.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as ProgressEvent);
    } catch {
      /* ignore malformed events */
    }
  };

  es.onerror = (err) => {
    onError?.(err);
  };

  return () => es.close();
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/documents/upload`, { method: 'POST', body: formData });
  return parseJsonResponse(res, 'Upload failed');
}

export async function listDocuments(): Promise<DocumentListItem[]> {
  const res = await fetch(`${API_BASE}/documents/list`);
  return parseJsonResponse(res, 'Failed to fetch documents');
}

export async function getDocumentStatus(id: string): Promise<DocumentStatusResponse> {
  const res = await fetch(`${API_BASE}/documents/${id}/status`);
  return parseJsonResponse(res, 'Failed to fetch status');
}

export async function getAnalysis(id: string): Promise<AnalysisResponse> {
  const res = await fetch(`${API_BASE}/documents/${id}/analysis`);
  return parseJsonResponse(res, 'Failed to fetch analysis');
}

export async function deleteDocument(id: string) {
  const res = await fetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' });
  return parseJsonResponse(res, 'Failed to delete document');
}

export interface ServerSettings {
  provider: string;
  model: string;
  configured: boolean;
  gemini_key_set: boolean;
  openrouter_key_set: boolean;
}

export async function getSettings(): Promise<ServerSettings> {
  const res = await fetch(`${API_BASE}/settings`);
  return parseJsonResponse(res, 'Failed to fetch settings');
}

export async function updateSettings(settings: { api_key: string, provider: string }) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  return parseJsonResponse(res, 'Failed to update settings');
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
}

export async function sendChatMessage(id: string, messages: ChatMessage[]): Promise<{ response: string }> {
  const res = await fetch(`${API_BASE}/documents/${id}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages })
  });
  return parseJsonResponse(res, 'Failed to send message');
}
