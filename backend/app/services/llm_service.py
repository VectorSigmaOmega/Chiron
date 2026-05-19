from __future__ import annotations

from functools import lru_cache
from json import JSONDecodeError
from uuid import uuid4

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, get_settings
from app.schemas.common import (
    AssistantResponse,
    Citation,
    EvidenceAssessment,
    EvidenceAssessmentResult,
    EvidenceCoverageDecision,
    EvidenceItem,
    EvidencePlan,
    NormalizedQuery,
    PlannedSubquestion,
    QueryConstraint,
    QueryEntity,
    RetrievalSpec,
    ScopeDecision,
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

    def _stub_normalize_query(self, *, question: str, session_context: dict) -> NormalizedQuery:
        trimmed = question.strip()
        normalized = " ".join(trimmed.split())
        lowered = normalized.lower()
        followup_prefixes = ("what about", "how about", "and what", "and how", "what if", "is it safe")
        context_entities = session_context.get("active_entities", [])
        active_terms = list(session_context.get("active_terms", []))
        entities: list[QueryEntity] = []
        for item in context_entities:
            try:
                entity = QueryEntity.model_validate(item)
            except ValidationError:
                continue
            entities.append(entity)
        session_context_used = False
        if session_context and any(lowered.startswith(prefix) for prefix in followup_prefixes):
            context_terms = active_terms or [entity.normalized_text for entity in entities]
            if context_terms:
                normalized = f"{normalized.rstrip('?')} in the context of {', '.join(context_terms[:3])}"
                session_context_used = True
        if not entities and normalized:
            entities.append(
                QueryEntity(
                    text=normalized,
                    normalized_text=normalized,
                    category="clinical_topic",
                    role="primary",
                    salience="primary",
                )
            )
        return NormalizedQuery(
            raw_question=question,
            normalized_question=normalized,
            intent_summary="Deterministic stub normalization for local test mode.",
            scope=ScopeDecision(in_scope=True, reason=None),
            needs_clarification=False,
            clarification_question=None,
            ambiguity_notes=[],
            entities=entities,
            constraints=[],
            recency_focus=any(token in normalized.lower() for token in ["latest", "recent", "current"]),
            session_context_used=session_context_used,
            normalization_notes=[],
        )

    def _stub_plan_evidence(self, *, normalized_query: NormalizedQuery, session_context: dict) -> EvidencePlan:
        text = normalized_query.normalized_question
        lowered = text.lower()
        entity_terms = [entity.normalized_text for entity in normalized_query.entities[:4]]
        population_terms = [
            entity.normalized_text
            for entity in normalized_query.entities
            if "population" in entity.category.lower() or "demographic" in (entity.role or "").lower()
        ][:3]
        must_concepts = [
            entity.normalized_text
            for entity in normalized_query.entities
            if any(token in entity.category.lower() for token in ["disease", "condition", "topic"])
        ][:3]
        focus_defaults = ["treatment"] if any(token in lowered for token in ["treatment", "management", "guideline", "first-line", "first line"]) else []
        specs = [
            RetrievalSpec(
                spec_id=str(uuid4()),
                lane="literature",
                objective="Retrieve supporting medical literature.",
                rationale="Literature search is the default retrieval lane in local stub mode.",
                query_text=text,
                source_query=None,
                focus_terms=entity_terms,
                must_concepts=must_concepts or entity_terms[:2],
                population_terms=population_terms,
                question_focus_terms=focus_defaults or ["clinical evidence"],
                recency_years=self.settings.pubmed_recency_years if normalized_query.recency_focus else None,
                desired_result_count=5,
                priority="high",
            )
        ]
        if any(token in lowered for token in ["treatment", "management", "guideline", "first-line", "first line"]):
            specs.insert(
                0,
                RetrievalSpec(
                    spec_id=str(uuid4()),
                    lane="guideline",
                    objective="Retrieve guideline or standard-of-care evidence.",
                    rationale="Treatment-style questions should check guidance in local stub mode.",
                    query_text=text,
                    source_query=None,
                    focus_terms=entity_terms,
                    must_concepts=must_concepts or entity_terms[:2],
                    population_terms=population_terms,
                    question_focus_terms=["treatment guidance", "standard of care"],
                    preferred_evidence_types=["guideline"],
                    recency_years=self.settings.pubmed_recency_years if normalized_query.recency_focus else None,
                    desired_result_count=2,
                    priority="high",
                ),
            )
        if any(token in lowered for token in ["latest", "recent", "trial", "investigational", "experimental"]):
            specs.append(
                RetrievalSpec(
                    spec_id=str(uuid4()),
                    lane="trials",
                    objective="Retrieve emerging or ongoing trial evidence.",
                    rationale="Recency-sensitive questions may benefit from trial registry evidence in local stub mode.",
                    query_text=text,
                    source_query=None,
                    focus_terms=entity_terms,
                    must_concepts=must_concepts or entity_terms[:2],
                    population_terms=population_terms,
                    question_focus_terms=["emerging evidence", "trials"],
                    preferred_evidence_types=["registry", "clinical trial"],
                    recency_years=self.settings.pubmed_recency_years if normalized_query.recency_focus else None,
                    desired_result_count=3,
                    priority="medium",
                )
            )
        if any(token in lowered for token in ["safety", "safe", "side effect", "warning", "adverse"]):
            specs.append(
                RetrievalSpec(
                    spec_id=str(uuid4()),
                    lane="drug_safety",
                    objective="Retrieve drug-label or safety evidence.",
                    rationale="Safety language is present in the question in local stub mode.",
                    query_text=text,
                    source_query=None,
                    focus_terms=entity_terms,
                    must_concepts=must_concepts or entity_terms[:2],
                    population_terms=population_terms,
                    question_focus_terms=["safety", "warnings", "adverse effects"],
                    intervention_terms=[
                        entity.normalized_text
                        for entity in normalized_query.entities
                        if entity.category.lower() in {"drug", "medication", "therapy", "intervention"}
                    ][:3],
                    preferred_evidence_types=["label", "drug safety"],
                    desired_result_count=3,
                    priority="medium",
                )
            )
        return EvidencePlan(
            normalized_question=text,
            primary_goal="Answer the user question with grounded evidence.",
            answer_strategy="Lead with the direct answer, then add caveats and emerging evidence if relevant.",
            subquestions=[PlannedSubquestion(question=text, priority="high")],
            retrieval_specs=specs,
        )

    def _stub_assess_evidence(
        self,
        *,
        normalized_query: NormalizedQuery,
        evidence_plan: EvidencePlan,
        evidence_items: list[EvidenceItem],
    ) -> EvidenceAssessmentResult:
        items: list[EvidenceAssessment] = []
        lowered_question = normalized_query.normalized_question.lower()
        for evidence in evidence_items:
            lowered = " ".join([evidence.title, evidence.key_claim, evidence.source_type]).lower()
            role = "supporting evidence"
            dimensions: list[str] = []
            if any(token in lowered_question for token in ["treatment", "management", "guideline"]):
                dimensions.append("direct answer")
            if any(token in lowered_question for token in ["safety", "safe", "warning", "adverse"]):
                dimensions.append("safety context")
            relevance = 50
            if evidence.source_type == "guideline":
                relevance += 25
                role = "guideline evidence"
            elif evidence.source_type == "review":
                relevance += 15
                role = "review evidence"
            elif evidence.source_type == "registry":
                relevance += 5
                role = "emerging evidence"
            include = True
            if "public health achievements" in lowered:
                include = False
                relevance = 10
                role = "off-target background"
            items.append(
                EvidenceAssessment(
                    evidence_id=evidence.evidence_id,
                    question_role=role,
                    claim_type=role,
                    applicability="direct evidence" if include else "background only",
                    supports_question_dimensions=dimensions,
                    semantic_relevance=max(0, min(100, relevance)),
                    include_in_answer=include,
                    assessment_summary="Deterministic stub assessment for local test mode.",
                )
            )
        return EvidenceAssessmentResult(items=items)

    def _stub_assess_coverage(
        self,
        *,
        normalized_query: NormalizedQuery,
        evidence_plan: EvidencePlan,
        evidence_items: list[EvidenceItem],
        completed_lanes: list[str],
        iteration: int,
    ) -> EvidenceCoverageDecision:
        if evidence_items:
            return EvidenceCoverageDecision(
                answerable_now=True,
                needs_follow_up=False,
                rationale="Stub mode considers the current evidence set sufficient once any evidence exists.",
                remaining_gaps=[],
                follow_up_specs=[],
            )
        return EvidenceCoverageDecision(
            answerable_now=False,
            needs_follow_up=False,
            rationale="Stub mode could not retrieve any evidence.",
            remaining_gaps=["no_retrieved_evidence"],
            follow_up_specs=[],
        )

    def _stub_verify_answer(self, *, draft_response: AssistantResponse) -> VerificationResult:
        if draft_response.status != "answered":
            return VerificationResult(
                status="abstain" if draft_response.status == "abstained" else "clarify",
                supported_claims=[],
                unsupported_claims=[],
                conflicts=[],
                abstention_class=draft_response.abstention_class,
                abstention_reason=draft_response.abstention_reason,
            )
        return VerificationResult(
            status="pass" if draft_response.citations else "abstain",
            supported_claims=[],
            unsupported_claims=[] if draft_response.citations else ["missing_citations"],
            conflicts=[],
            abstention_class=None if draft_response.citations else "insufficient_evidence",
            abstention_reason=None if draft_response.citations else "Draft answer does not include citations.",
        )

    def normalize_query(self, *, question: str, session_context: dict) -> NormalizedQuery | None:
        if not self._client:
            return self._stub_normalize_query(question=question, session_context=session_context)
        model = self.settings.gemini_query_model or self.settings.gemini_model
        prompt = f"""
You are the first semantic step for a clinician-facing medical evidence system.

Return a NormalizedQuery object.

Goals:
- clean up spelling, phrasing, and shorthand without changing medical intent
- expand abbreviations or acronyms only when the intended meaning is highly likely from context
- produce a cleaner search-oriented medical question
- identify open-ended entities and constraints from the question and session context
- decide whether the question is in scope for a medical evidence assistant
- decide whether a clarification question is required before evidence gathering

Important rules:
- do not use fixed medical vocabularies or hardcoded modifier lists
- entity and constraint categories should be concise free-text labels chosen from the question itself
- preserve ambiguity when it is real; do not over-normalize uncertain shorthand
- if this is a follow-up, use the session context to recover omitted clinical context
- if the question is out of scope, mark scope.in_scope as false and explain briefly
- if clarification is needed, set needs_clarification true and provide a concise clarification_question
- recency_focus should be true only when the user explicitly asks for recent, current, latest, or ongoing evidence

Session context:
{session_context}

Question:
{question}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=NormalizedQuery)
        return result if isinstance(result, NormalizedQuery) else None

    def plan_evidence(self, *, normalized_query: NormalizedQuery, session_context: dict) -> EvidencePlan | None:
        if not self._client:
            return self._stub_plan_evidence(normalized_query=normalized_query, session_context=session_context)
        model = self.settings.gemini_planning_model or self.settings.gemini_model
        prompt = f"""
You are the evidence-planning step for a clinician-facing medical evidence system.

Return an EvidencePlan object.

Available retrieval lanes:
- guideline
- literature
- trials
- drug_safety

Your job:
- decide the primary goal for answering the question
- break the question into subquestions only where it helps answer quality
- choose only the retrieval lanes that materially help
- generate retrieval_specs for each chosen lane
- use query_text to describe the retrieval goal in plain language for logging and debugging
- fill the structured retrieval fields so connectors can compile source-native queries

Planning rules:
- treatment questions should usually prioritize guideline and literature lanes before trial details
- trial evidence should supplement rather than dominate unless the user explicitly asks about investigational or ongoing work
- drug_safety should be used only when the question asks about risks, warnings, adverse effects, contraindications, interactions, or a specific medication
- must_concepts should contain the core disease, condition, or topic concepts that must be present
- population_terms should contain patient-group or context terms like pregnancy, pediatrics, HIV, or postpartum when relevant
- intervention_terms should contain named drugs, regimens, procedures, or exposures when relevant
- question_focus_terms should contain the semantic focus of the question such as treatment, diagnosis, prevention, safety, prognosis, or screening
- supporting_concepts may add narrower concepts that improve relevance but are not mandatory
- exclude_concepts may be used sparingly to prevent obvious drift
- preferred_evidence_types should express source preferences like guideline, review, clinical trial, registry, label, or observational study when useful
- source_query is optional legacy/debug text; do not rely on raw boolean syntax as the main contract
- focus_terms may be a compact summary of the most salient phrases, but the structured fields are primary
- retrieval specs must stay faithful to the normalized question and should not introduce new clinical assumptions
- do not use hardcoded disease or modifier lists

Session context:
{session_context}

Normalized query:
{normalized_query.model_dump(mode="json")}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=EvidencePlan)
        return result if isinstance(result, EvidencePlan) else None

    def assess_evidence(
        self,
        *,
        normalized_query: NormalizedQuery,
        evidence_plan: EvidencePlan,
        evidence_items: list[EvidenceItem],
    ) -> EvidenceAssessmentResult | None:
        if not self._client:
            return self._stub_assess_evidence(
                normalized_query=normalized_query,
                evidence_plan=evidence_plan,
                evidence_items=evidence_items,
            )
        model = self.settings.gemini_verifier_model or self.settings.gemini_model
        prompt = f"""
You are ranking and characterizing retrieved evidence for a clinician-facing evidence assistant.

Return an EvidenceAssessmentResult object.

For each evidence item:
- assign an open-ended question_role phrase that describes how it should be used
- assign an open-ended claim_type phrase
- assign an open-ended applicability phrase that explains how directly it matches the question
- fill supports_question_dimensions with short free-text dimensions or subquestions this evidence helps answer
- assign semantic_relevance from 0 to 100
- set include_in_answer true only if the evidence should materially shape the final answer
- provide a concise assessment_summary

Important rules:
- do not use fixed disease vocabularies or hardcoded modifier logic
- prefer direct evidence that answers the user question over broad background context
- treatment questions should privilege evidence that states what should be done clinically
- trial registry entries can be useful but should usually be treated as emerging evidence rather than standard-of-care evidence unless the user explicitly asks for trials
- do not omit any evidence_id

Normalized query:
{normalized_query.model_dump(mode="json")}

Evidence plan:
{evidence_plan.model_dump(mode="json")}

Evidence items:
{[item.model_dump(mode='json') for item in evidence_items]}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=EvidenceAssessmentResult)
        return result if isinstance(result, EvidenceAssessmentResult) else None

    def assess_coverage(
        self,
        *,
        normalized_query: NormalizedQuery,
        evidence_plan: EvidencePlan,
        evidence_items: list[EvidenceItem],
        completed_lanes: list[str],
        iteration: int,
    ) -> EvidenceCoverageDecision | None:
        if not self._client:
            return self._stub_assess_coverage(
                normalized_query=normalized_query,
                evidence_plan=evidence_plan,
                evidence_items=evidence_items,
                completed_lanes=completed_lanes,
                iteration=iteration,
            )
        model = self.settings.gemini_coverage_model or self.settings.gemini_model
        prompt = f"""
You are deciding whether a clinician-facing evidence workflow should do more retrieval work.

Return an EvidenceCoverageDecision object.

Your job:
- decide whether the current evidence is enough to answer safely
- decide whether more retrieval is needed
- if more retrieval is needed, propose follow_up_specs using the same retrieval lane model as EvidencePlan
- explain remaining gaps in free text

Important rules:
- use only available lanes: guideline, literature, trials, drug_safety
- do not create follow-up work unless it would materially improve answer quality
- treatment questions should not drift into speculative trial details unless those details are genuinely useful
- do not use hardcoded disease or modifier lists
- respect the current iteration and keep the follow-up set focused

Normalized query:
{normalized_query.model_dump(mode="json")}

Evidence plan:
{evidence_plan.model_dump(mode="json")}

Completed lanes:
{completed_lanes}

Iteration:
{iteration}

Evidence items:
{[item.model_dump(mode='json') for item in evidence_items]}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=EvidenceCoverageDecision)
        return result if isinstance(result, EvidenceCoverageDecision) else None

    def synthesize_answer(
        self,
        *,
        normalized_query: NormalizedQuery,
        evidence_plan: EvidencePlan,
        evidence_items: list[EvidenceItem],
        citations: list[Citation],
    ) -> SynthesisDraft | None:
        if not self._client:
            if not evidence_items:
                return None
            lead = evidence_items[0]
            return SynthesisDraft(
                answer=lead.key_claim,
                evidence_summary=[item.key_claim for item in evidence_items[:3]],
                evidence_strength="moderate" if any(item.evidence_strength in {"high", "moderate"} for item in evidence_items) else "low",
                limitations=["Local stub synthesis is active; production-quality phrasing requires Gemini."],
            )
        model = self.settings.gemini_synthesis_model or self.settings.gemini_model
        prompt = f"""
You are drafting a clinician-facing answer from grounded evidence.

Return a SynthesisDraft object.

Requirements:
- use only the supplied evidence items
- answer the user's core question directly in the first sentence
- do not invent facts, drugs, regimens, or study findings
- do not introduce medical assumptions that are not present in the evidence
- separate the direct answer from caveats and uncertainty
- if emerging trial evidence is included, present it as supplementary context rather than the main answer unless the user explicitly asked for trials
- evidence_strength must be one of: high, moderate, low, unknown

Normalized query:
{normalized_query.model_dump(mode="json")}

Evidence plan:
{evidence_plan.model_dump(mode="json")}

Evidence items:
{[item.model_dump(mode='json') for item in evidence_items]}

Available citations:
{[citation.model_dump(mode='json') for citation in citations]}
""".strip()
        result = self._call_structured(model=model, prompt=prompt, schema_model=SynthesisDraft)
        return result if isinstance(result, SynthesisDraft) else None

    def verify_answer(
        self,
        *,
        normalized_query: NormalizedQuery,
        evidence_plan: EvidencePlan,
        draft_response: AssistantResponse,
        evidence_items: list[EvidenceItem],
    ) -> VerificationResult | None:
        if not self._client:
            return self._stub_verify_answer(draft_response=draft_response)
        model = self.settings.gemini_verifier_model or self.settings.gemini_model
        prompt = f"""
You are the verification gate for a clinician-facing evidence assistant.

Return a VerificationResult object.

Allowed statuses:
- pass
- clarify
- abstain

Verification rules:
- verify that the draft answer stays within the evidence
- prefer narrow grounded answers over broad speculative ones
- mark unsupported claims explicitly
- use clarify when the answer needs more clinical context from the user
- use abstain when the evidence is too weak, too conflicting, or too indirect to support a safe answer
- conflicts should be stated in concise free text

Normalized query:
{normalized_query.model_dump(mode="json")}

Evidence plan:
{evidence_plan.model_dump(mode="json")}

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
