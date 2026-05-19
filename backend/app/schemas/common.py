from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class Citation(BaseModel):
    label: str
    source_id: str
    title: str
    url: str
    publication_date: date | None = None
    source_type: str | None = None
    publisher: str | None = None
    snippet: str | None = None


class QueryEntity(BaseModel):
    text: str
    normalized_text: str
    category: str
    role: str | None = None
    salience: str | None = None


class QueryConstraint(BaseModel):
    text: str
    normalized_text: str | None = None
    category: str
    importance: str = "primary"


class ScopeDecision(BaseModel):
    in_scope: bool = True
    reason: str | None = None


class NormalizationNote(BaseModel):
    original_text: str
    normalized_text: str
    reason: str | None = None


class NormalizedQuery(BaseModel):
    raw_question: str
    normalized_question: str
    intent_summary: str
    scope: ScopeDecision = Field(default_factory=ScopeDecision)
    needs_clarification: bool = False
    clarification_question: str | None = None
    ambiguity_notes: list[str] = Field(default_factory=list)
    entities: list[QueryEntity] = Field(default_factory=list)
    constraints: list[QueryConstraint] = Field(default_factory=list)
    recency_focus: bool = False
    session_context_used: bool = False
    normalization_notes: list[NormalizationNote] = Field(default_factory=list)


class PlannedSubquestion(BaseModel):
    question: str
    priority: str = "medium"
    success_criteria: str | None = None


class RetrievalSpec(BaseModel):
    spec_id: str
    lane: str
    objective: str
    rationale: str
    query_text: str
    source_query: str
    focus_terms: list[str] = Field(default_factory=list)
    desired_result_count: int = 5
    priority: str = "medium"
    depends_on: list[str] = Field(default_factory=list)


class EvidencePlan(BaseModel):
    normalized_question: str
    primary_goal: str
    answer_strategy: str
    subquestions: list[PlannedSubquestion] = Field(default_factory=list)
    retrieval_specs: list[RetrievalSpec] = Field(default_factory=list)


class SourceDocument(BaseModel):
    source_id: str
    source_type: str
    title: str
    url: str
    publication_date: date | None = None
    publisher: str | None = None
    abstract: str | None = None
    full_text: str | None = None
    metadata: dict = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    source_type: str
    title: str
    url: str
    publication_date: date | None = None
    publisher: str | None = None
    population: str | None = None
    intervention: str | None = None
    outcome: str | None = None
    key_claim: str
    claim_type: str | None = None
    applicability: str | None = None
    supports_question_dimensions: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    evidence_strength: str = "unknown"
    source_priority: int = 0
    extracted_entities: list[str] = Field(default_factory=list)
    question_role: str | None = None
    semantic_relevance: int | None = None
    include_in_answer: bool | None = None
    assessment_summary: str | None = None


class SpecialistTask(BaseModel):
    task_id: str
    agent_type: str
    objective: str
    query_text: str
    source_query: str
    rationale: str | None = None
    focus_terms: list[str] = Field(default_factory=list)
    priority: str = "medium"
    desired_result_count: int = 5
    depends_on: list[str] = Field(default_factory=list)


class EvidenceCoverageDecision(BaseModel):
    answerable_now: bool
    needs_follow_up: bool = False
    rationale: str
    remaining_gaps: list[str] = Field(default_factory=list)
    follow_up_specs: list[RetrievalSpec] = Field(default_factory=list)


class VerifiedClaim(BaseModel):
    claim_text: str
    supporting_source_ids: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: str
    supported_claims: list[VerifiedClaim] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    abstention_class: str | None = None
    abstention_reason: str | None = None


class EvidenceAssessment(BaseModel):
    evidence_id: str
    question_role: str | None = None
    claim_type: str | None = None
    applicability: str | None = None
    supports_question_dimensions: list[str] = Field(default_factory=list)
    semantic_relevance: int = Field(ge=0, le=100)
    include_in_answer: bool = True
    assessment_summary: str | None = None


class EvidenceAssessmentResult(BaseModel):
    items: list[EvidenceAssessment] = Field(default_factory=list)


class AssistantResponse(BaseModel):
    status: str
    answer: str | None = None
    clarification_question: str | None = None
    abstention_class: str | None = None
    abstention_reason: str | None = None
    evidence_summary: list[str] = Field(default_factory=list)
    evidence_strength: str | None = None
    limitations: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    last_literature_check_at: datetime | None = None
