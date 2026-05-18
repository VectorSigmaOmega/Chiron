from __future__ import annotations

from functools import lru_cache
from json import JSONDecodeError

from google import genai
from pydantic import BaseModel, Field, ValidationError
from google.genai import types

from app.core.config import Settings, get_settings
from app.schemas.common import (
    AssistantResponse,
    Citation,
    EvidenceAssessmentResult,
    EvidenceItem,
    InformationNeed,
    ParsedQuery,
    VerificationResult,
)


class SynthesisDraft(BaseModel):
    answer: str
    evidence_summary: list[str] = Field(default_factory=list)
    evidence_strength: str = "unknown"
    limitations: list[str] = Field(default_factory=list)


class LLMService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: genai.Client | None = None
        if self.settings.llm_mode == "gemini" and self.settings.gemini_api_key:
            self._client = genai.Client(api_key=self.settings.gemini_api_key)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _call_structured(self, *, model: str, prompt: str, schema_model: type[BaseModel]) -> BaseModel | None:
        if not self._client:
            return None
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema_model,
                temperature=0,
            ),
        )
        if isinstance(response.parsed, schema_model):
            return response.parsed
        if response.parsed is not None:
            try:
                return schema_model.model_validate(response.parsed)
            except ValidationError:
                pass
        try:
            return schema_model.model_validate_json(response.text)
        except (ValidationError, JSONDecodeError, TypeError):
            return None

    def parse_query(self, *, question: str, session_context: dict) -> ParsedQuery | None:
        model = self.settings.gemini_query_model or self.settings.gemini_model
        prompt = f"""
You are parsing a clinician's medical evidence query for an orchestration system.

Return a ParsedQuery object that:
- rewrites the question into a cleaner search-oriented form
- extracts medical entities
- extracts clinical_modifiers for population constraints, comorbidities, immunologic status, resistance status, pregnancy/lactation, and care-setting qualifiers when present
- detects if clarification is required
- when the question is a follow-up, use the session context to resolve omitted condition, modifier, or medication context
- sets information_needs using only these values:
  - literature
  - guidelines
  - drug_safety
  - trials
- uses concise clarification questions only when needed for safety
- when clarification is needed for common syndromic questions like pneumonia, explicitly ask for patient population and care setting
- marks recency_required true when the user asks for latest, current, recent, or similar wording
- set scope_assessment to out_of_scope for insurance, billing, prior authorization, coverage, or non-medical administrative questions

Session context:
{session_context}

Question:
{question}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=ParsedQuery)
        return result if isinstance(result, ParsedQuery) else None

    def synthesize_answer(
        self,
        *,
        parsed_query: ParsedQuery,
        evidence_items: list[EvidenceItem],
        citations: list[Citation],
    ) -> SynthesisDraft | None:
        model = self.settings.gemini_synthesis_model or self.settings.gemini_model
        prompt = f"""
You are drafting a cautious medical evidence summary.

Requirements:
- Use only the supplied evidence.
- Do not invent facts.
- Be explicit about uncertainty.
- Keep the answer concise and clinician-facing.
- Do not include citation labels inside the answer; citations are attached separately.
- Prefer guideline-backed or review-backed conclusions over single studies when they conflict.
- If evidence is indirect for the requested population, say so explicitly.
- Do not mention a drug, regimen, warning, study result, or comparison unless it appears in the supplied evidence items.
- If the evidence only supports a narrow answer, answer narrowly rather than generalizing.
- Start by answering the user's core question directly in the first sentence.
- For treatment questions, state the current treatment position before giving caveats or uncertainty.
- If the evidence mainly addresses a narrower subtype than the user asked about, say that explicitly instead of silently generalizing.
- Separate treatment position, safety considerations, and uncertainty clearly.
- evidence_strength must be one of: high, moderate, low, unknown

Parsed query:
{parsed_query.model_dump(mode="json")}

Evidence items:
{[item.model_dump(mode='json') for item in evidence_items]}

Available citations:
{[citation.model_dump(mode='json') for citation in citations]}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=SynthesisDraft)
        return result if isinstance(result, SynthesisDraft) else None

    def assess_evidence(
        self,
        *,
        parsed_query: ParsedQuery,
        evidence_items: list[EvidenceItem],
    ) -> EvidenceAssessmentResult | None:
        model = self.settings.gemini_verifier_model or self.settings.gemini_model
        prompt = f"""
You are ranking retrieved medical evidence for a clinician-facing evidence assistant.

For each supplied evidence item:
- assign question_role using only:
  - treatment
  - safety
  - trial_status
  - background
  - uncertainty
  - exclude
- assign semantic_relevance from 0 to 100

Guidance:
- Use treatment when the source directly helps answer what to do clinically.
- Use safety when the source mainly informs adverse effects, warnings, contraindications, or toxicity.
- Use trial_status when the source mainly informs ongoing or emerging trial evidence.
- Use uncertainty when the source is relevant mainly because it limits or qualifies the answer.
- Use background for context that is relevant but should not drive the lead answer.
- Use exclude for weakly related or off-target evidence that should not shape the answer.
- Prefer direct population/modifier matches over indirect evidence.
- Prefer evidence that directly addresses the asked clinical condition and question intent.
- Do not omit any evidence_id from the result.

Parsed query:
{parsed_query.model_dump(mode="json")}

Evidence items:
{[item.model_dump(mode='json') for item in evidence_items]}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=EvidenceAssessmentResult)
        return result if isinstance(result, EvidenceAssessmentResult) else None

    def verify_answer(
        self,
        *,
        parsed_query: ParsedQuery,
        draft_response: AssistantResponse,
        evidence_items: list[EvidenceItem],
    ) -> VerificationResult | None:
        model = self.settings.gemini_verifier_model or self.settings.gemini_model
        prompt = f"""
You are a verification step for a medical evidence assistant.

Decide whether the answer should pass, request clarification, or abstain.
Use only these statuses:
- pass
- clarify
- abstain

Use only these abstention classes when applicable:
- insufficient_evidence
- conflicting_evidence
- missing_clinical_context
- coverage_gap
- recency_gap
- ambiguous_query

Check whether the draft answer is adequately supported by the evidence items and whether the question required more context.
- Pay particular attention to population mismatch, recency-sensitive questions, and safety questions answered without direct safety evidence.

Parsed query:
{parsed_query.model_dump(mode="json")}

Draft response:
{draft_response.model_dump(mode="json")}

Evidence items:
{[item.model_dump(mode='json') for item in evidence_items]}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=VerificationResult)
        return result if isinstance(result, VerificationResult) else None


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()
