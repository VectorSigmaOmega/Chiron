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


class EntityRef(BaseModel):
    name: str
    kind: str = "medical_concept"


class InformationNeed(BaseModel):
    name: str
    reason: str


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


class ParsedQuery(BaseModel):
    original_question: str
    rewritten_question: str
    entities: list[EntityRef] = Field(default_factory=list)
    population: str | None = None
    setting: str | None = None
    pregnancy_status: str | None = None
    comorbidities: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    recency_required: bool = False
    missing_dimensions: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    information_needs: list[InformationNeed] = Field(default_factory=list)
    scope_assessment: str = "in_scope"
    scope_reason: str | None = None


class SpecialistTask(BaseModel):
    task_id: str
    agent_type: str
    goal: str
    subquery: str
    depends_on: list[str] = Field(default_factory=list)
    focus_entities: list[str] = Field(default_factory=list)


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
