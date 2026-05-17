"""
LexGuard Data Models — Pydantic schemas for documents, clauses, risks, and analyses.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


# ──────────────────────── Enums ────────────────────────

class DocumentStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class ClauseType(str, Enum):
    DEFINITIONAL = "DEFINITIONAL"
    RIGHTS_GRANTED = "RIGHTS_GRANTED"
    OBLIGATIONS = "OBLIGATIONS"
    RESTRICTIONS = "RESTRICTIONS"
    PAYMENT_TERMS = "PAYMENT_TERMS"
    FEE_STRUCTURES = "FEE_STRUCTURES"
    PENALTIES = "PENALTIES"
    REFUND_CANCELLATION = "REFUND_CANCELLATION"
    IP_OWNERSHIP = "IP_OWNERSHIP"
    LICENSE_GRANTS = "LICENSE_GRANTS"
    NON_COMPETE = "NON_COMPETE"
    NON_SOLICITATION = "NON_SOLICITATION"
    CONFIDENTIALITY = "CONFIDENTIALITY"
    IP_ASSIGNMENT = "IP_ASSIGNMENT"
    LIABILITY_LIMITATION = "LIABILITY_LIMITATION"
    INDEMNIFICATION = "INDEMNIFICATION"
    WARRANTY_DISCLAIMER = "WARRANTY_DISCLAIMER"
    DISPUTE_RESOLUTION = "DISPUTE_RESOLUTION"
    DATA_COLLECTION = "DATA_COLLECTION"
    DATA_USAGE = "DATA_USAGE"
    THIRD_PARTY_SHARING = "THIRD_PARTY_SHARING"
    DATA_RETENTION = "DATA_RETENTION"
    TERMINATION = "TERMINATION"
    AUTO_RENEWAL = "AUTO_RENEWAL"
    CANCELLATION_PENALTY = "CANCELLATION_PENALTY"
    SURVIVAL_CLAUSES = "SURVIVAL_CLAUSES"
    GOVERNING_LAW = "GOVERNING_LAW"
    AMENDMENT = "AMENDMENT"
    ASSIGNMENT = "ASSIGNMENT"
    FORCE_MAJEURE = "FORCE_MAJEURE"
    OTHER = "OTHER"


class RiskCategory(str, Enum):
    FINANCIAL = "FINANCIAL"
    EMPLOYMENT = "EMPLOYMENT"
    LEGAL_LIABILITY = "LEGAL_LIABILITY"
    PRIVACY = "PRIVACY"
    OPERATIONAL = "OPERATIONAL"
    INTELLECTUAL_PROPERTY = "INTELLECTUAL_PROPERTY"


# ──────────────────────── Sub-Models ────────────────────────

class FinancialExposure(BaseModel):
    amount: Optional[float] = None
    currency: str = "USD"
    scenario: str = ""


class ContributingFactor(BaseModel):
    factor: str
    contribution: float = 0.0  # percentage
    explanation: str = ""


class SupportingEvidence(BaseModel):
    type: str  # market_comparison, precedent, etc.
    content: str


class Recommendation(BaseModel):
    action: str
    suggested_language: Optional[str] = None
    priority: int = 5  # 1 = highest


class UserImpact(BaseModel):
    financial: str = ""
    operational: str = ""
    legal: str = ""


# ──────────────────────── Core Models ────────────────────────

class ExtractedClause(BaseModel):
    id: str = Field(default_factory=lambda: f"clause_{uuid.uuid4().hex[:8]}")
    type: str = "OTHER"
    section_reference: str = ""
    text: str
    key_terms: list[str] = []
    parties_affected: list[str] = []
    ambiguities: list[str] = []
    confidence_score: float = 0.0


class RiskAnalysis(BaseModel):
    clause_id: str
    primary_category: str = "FINANCIAL"
    subcategory: str = ""
    severity_score: float = 0.0
    severity_level: str = "LOW"
    severity_reasoning: str = ""
    likelihood_percentage: float = 0.0
    likelihood_reasoning: str = ""
    parties_affected: list[str] = []
    financial_exposure: Optional[FinancialExposure] = None
    legal_exposure: str = ""
    market_comparison: str = ""
    ambiguities: list[str] = []
    recommendations: list[Recommendation] = []
    contributing_factors: list[ContributingFactor] = []
    supporting_evidence: list[SupportingEvidence] = []
    user_impact: Optional[UserImpact] = None


class Scenario(BaseModel):
    trigger: str
    financial_impact: Optional[FinancialExposure] = None
    legal_implications: str = ""
    timeline: str = ""
    mitigations: list[str] = []


class ImplicationsResult(BaseModel):
    clause_id: str
    scenarios: list[Scenario] = []


class AmbiguityResult(BaseModel):
    clause_id: str
    ambiguities: list[dict] = []
    contradictions: list[dict] = []
    clarification_recommendations: list[str] = []


class MarketBenchmarkResult(BaseModel):
    clause_id: str
    prevalence_percentage: float = 0.0
    deviation_level: str = "STANDARD"  # STANDARD, STRICTER, LOOSER
    market_norm_description: str = ""
    fair_alternative: str = ""


class PrivacyComplianceResult(BaseModel):
    clause_id: str
    gdpr_compliant: bool = True
    ccpa_compliant: bool = True
    violations: list[str] = []
    required_consents: list[str] = []


class RelationshipMappingResult(BaseModel):
    clause_id: str
    depends_on: list[str] = []  # other clause IDs
    conflicts_with: list[str] = []
    compound_risk_description: str = ""


class NegotiationGuidanceResult(BaseModel):
    clause_id: str
    leverage_points: list[str] = []
    trade_off_options: list[str] = []
    walk_away_threshold: str = ""
    suggested_redline: str = ""


# ──────────────────────── Document Models ────────────────────────

class DocumentMetadata(BaseModel):
    author: Optional[str] = None
    creation_date: Optional[str] = None
    page_count: int = 0
    word_count: int = 0
    file_type: str = ""
    file_size_bytes: int = 0


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    message: str


class DocumentRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    filename: str
    original_filename: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    file_type: str
    status: DocumentStatus = DocumentStatus.UPLOADING
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    raw_text: str = ""
    normalized_text: str = ""
    sections: list[dict] = []
    extracted_clauses: list[ExtractedClause] = []
    risk_analyses: list[RiskAnalysis] = []
    implications: list[ImplicationsResult] = []
    ambiguities: list[AmbiguityResult] = []
    market_benchmarks: list[MarketBenchmarkResult] = []
    privacy_compliance: list[PrivacyComplianceResult] = []
    relationships: list[RelationshipMappingResult] = []
    negotiation_guidance: list[NegotiationGuidanceResult] = []
    overall_risk_score: float = 0.0
    overall_severity: str = "LOW"
    signing_recommendation: str = ""
    key_findings: list[str] = []
    processing_time_seconds: float = 0.0
    error_message: Optional[str] = None


# ──────────────────────── Analysis Summary ────────────────────────

class RiskSummary(BaseModel):
    overall_score: float = 0.0
    severity_level: str = "LOW"
    signing_recommendation: str = "Proceed"
    total_clauses: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    none_count: int = 0
    key_findings: list[str] = []
    risk_by_category: dict[str, int] = {}
    processing_time: float = 0.0


class AnalysisResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    risk_summary: Optional[RiskSummary] = None
    clauses: list[ExtractedClause] = []
    risk_analyses: list[RiskAnalysis] = []
    implications: list[ImplicationsResult] = []
    ambiguities: list[AmbiguityResult] = []
    market_benchmarks: list[MarketBenchmarkResult] = []
    privacy_compliance: list[PrivacyComplianceResult] = []
    relationships: list[RelationshipMappingResult] = []
    negotiation_guidance: list[NegotiationGuidanceResult] = []


class DocumentListItem(BaseModel):
    id: str
    filename: str
    upload_date: datetime
    file_type: str
    status: DocumentStatus
    overall_risk_score: float = 0.0
    overall_severity: str = "LOW"
    clause_count: int = 0
    page_count: int = 0


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class ChatResponse(BaseModel):
    response: str
