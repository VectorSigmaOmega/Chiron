from app.orchestration import nodes
from app.schemas.common import (
    EvidenceAssessment,
    EvidenceAssessmentResult,
    EvidenceItem,
    EvidencePlan,
    NormalizedQuery,
    ScopeDecision,
)


def _normalized_query(question: str, *, recency_focus: bool = False) -> NormalizedQuery:
    return NormalizedQuery(
        raw_question=question,
        normalized_question=question,
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
        recency_focus=recency_focus,
    )


def _evidence_plan(question: str) -> EvidencePlan:
    return EvidencePlan(
        normalized_question=question,
        primary_goal="Answer the clinical question.",
        answer_strategy="Direct answer first.",
        subquestions=[],
        retrieval_specs=[],
    )


def test_order_evidence_items_uses_llm_assessment_to_promote_core_evidence(monkeypatch) -> None:
    normalized_query = _normalized_query("Latest treatment for tuberculosis in pregnancy")
    evidence_plan = _evidence_plan(normalized_query.normalized_question)
    background_review = EvidenceItem(
        evidence_id="ev-background",
        source_id="src-background",
        source_type="review",
        title="Global tuberculosis burden overview",
        url="https://example.com/background",
        key_claim="Tuberculosis remains a major cause of maternal morbidity globally.",
        evidence_strength="moderate",
        source_priority=3,
    )
    treatment_study = EvidenceItem(
        evidence_id="ev-treatment",
        source_id="src-treatment",
        source_type="study",
        title="Treatment outcomes for tuberculosis in pregnancy",
        url="https://example.com/treatment",
        key_claim="Standard evidence-based regimens remain the default approach for active tuberculosis in pregnancy when drug susceptibility is expected.",
        evidence_strength="low",
        source_priority=2,
    )

    monkeypatch.setattr(
        nodes.llm_service,
        "assess_evidence",
        lambda **_: EvidenceAssessmentResult(
            items=[
                EvidenceAssessment(
                    evidence_id="ev-background",
                    question_role="background context",
                    claim_type="background context",
                    applicability="background only",
                    supports_question_dimensions=["context"],
                    semantic_relevance=30,
                    include_in_answer=False,
                    assessment_summary="Off-target background review.",
                ),
                EvidenceAssessment(
                    evidence_id="ev-treatment",
                    question_role="direct treatment evidence",
                    claim_type="direct treatment evidence",
                    applicability="direct match",
                    supports_question_dimensions=["treatment answer"],
                    semantic_relevance=90,
                    include_in_answer=True,
                    assessment_summary="Directly answers the treatment question.",
                ),
            ]
        ),
    )

    ordered = nodes._order_evidence_items(normalized_query, evidence_plan, [background_review, treatment_study])

    assert ordered[0].evidence_id == "ev-treatment"
    assert ordered[0].question_role == "direct treatment evidence"
    assert ordered[0].semantic_relevance == 90


def test_select_synthesis_evidence_prefers_items_marked_for_answer() -> None:
    items = [
        EvidenceItem(
            evidence_id="ev-treatment",
            source_id="src1",
            source_type="guideline",
            title="Treatment guidance",
            url="https://example.com/treatment",
            key_claim="Use standard evidence-based regimens.",
            include_in_answer=True,
        ),
        EvidenceItem(
            evidence_id="ev-trial",
            source_id="src2",
            source_type="registry",
            title="Trial registry record",
            url="https://example.com/trial",
            key_claim="Emerging trial record.",
            include_in_answer=False,
        ),
        EvidenceItem(
            evidence_id="ev-safety",
            source_id="src4",
            source_type="label",
            title="Safety label",
            url="https://example.com/safety",
            key_claim="Hepatotoxicity warning.",
            include_in_answer=True,
        ),
    ]

    selected = nodes._select_synthesis_evidence(items)

    assert [item.evidence_id for item in selected] == ["ev-treatment", "ev-safety"]


def test_apply_verification_guardrails_keeps_recent_citation_requirement_generic() -> None:
    normalized_query = _normalized_query("Latest treatment for tuberculosis in pregnancy", recency_focus=True)
    evidence_plan = _evidence_plan(normalized_query.normalized_question)
    evidence = [
        EvidenceItem(
            evidence_id="ev-old",
            source_id="src-old",
            source_type="review",
            title="Old review",
            url="https://example.com/old",
            key_claim="Older evidence.",
            source_priority=3,
            evidence_strength="moderate",
        )
    ]
    draft = nodes.AssistantResponse(
        status="answered",
        answer="Older evidence only.",
        citations=[],
        evidence_summary=[],
        limitations=[],
        evidence_items=evidence,
        last_literature_check_at=None,
    )
    verification = nodes.VerificationResult(
        status="pass",
        supported_claims=[],
        unsupported_claims=[],
        conflicts=[],
    )

    guarded = nodes._apply_verification_guardrails(normalized_query, evidence_plan, draft, verification, evidence)

    assert guarded.status == "abstain"
    assert guarded.abstention_class == "recency_gap"
