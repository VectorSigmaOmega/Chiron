from app.orchestration import nodes
from app.schemas.common import EvidenceAssessment, EvidenceAssessmentResult, EvidenceItem, ParsedQuery


def test_order_evidence_items_uses_llm_assessment_to_promote_core_evidence(monkeypatch) -> None:
    parsed_query = ParsedQuery(
        original_question="Latest treatment for tuberculosis in pregnancy",
        rewritten_question="Latest treatment for tuberculosis in pregnancy",
        clinical_modifiers=["pregnancy"],
        population="pregnancy",
    )
    background_review = EvidenceItem(
        evidence_id="ev-background",
        source_id="src-background",
        source_type="review",
        title="Global tuberculosis burden overview",
        url="https://example.com/background",
        key_claim="Tuberculosis remains a major cause of maternal morbidity globally.",
        claim_type="background",
        applicability="indirect",
        supports_question_dimensions=["recency"],
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
        claim_type="treatment",
        applicability="direct",
        supports_question_dimensions=["treatment", "population"],
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
                    question_role="background",
                    semantic_relevance=30,
                ),
                EvidenceAssessment(
                    evidence_id="ev-treatment",
                    question_role="treatment",
                    semantic_relevance=90,
                ),
            ]
        ),
    )

    ordered = nodes._order_evidence_items(parsed_query, [background_review, treatment_study])

    assert ordered[0].evidence_id == "ev-treatment"
    assert ordered[0].question_role == "treatment"
    assert ordered[0].semantic_relevance == 90


def test_select_synthesis_evidence_filters_mixed_roles_for_treatment_questions() -> None:
    parsed_query = ParsedQuery(
        original_question="Latest treatment for tuberculosis in pregnancy",
        rewritten_question="Latest treatment for tuberculosis in pregnancy",
    )
    items = [
        EvidenceItem(
            evidence_id="ev-treatment",
            source_id="src1",
            source_type="guideline",
            title="Treatment guidance",
            url="https://example.com/treatment",
            key_claim="Use standard evidence-based regimens.",
            question_role="treatment",
        ),
        EvidenceItem(
            evidence_id="ev-trial",
            source_id="src2",
            source_type="registry",
            title="Trial registry record",
            url="https://example.com/trial",
            key_claim="Emerging trial record.",
            question_role="trial_status",
        ),
        EvidenceItem(
            evidence_id="ev-exclude",
            source_id="src3",
            source_type="study",
            title="Off-target paper",
            url="https://example.com/exclude",
            key_claim="Weakly related context.",
            question_role="exclude",
        ),
        EvidenceItem(
            evidence_id="ev-safety",
            source_id="src4",
            source_type="label",
            title="Safety label",
            url="https://example.com/safety",
            key_claim="Hepatotoxicity warning.",
            question_role="safety",
        ),
    ]

    selected = nodes._select_synthesis_evidence(parsed_query, items)

    assert [item.evidence_id for item in selected] == ["ev-treatment", "ev-safety"]


def test_primary_dimension_keeps_latest_treatment_queries_as_treatment() -> None:
    parsed_query = ParsedQuery(
        original_question="Latest treatment for tuberculosis in pregnancy",
        rewritten_question="Latest treatment for tuberculosis in pregnancy",
        recency_required=True,
    )
    assert nodes._primary_question_dimension(parsed_query) == "treatment"

    trials_query = ParsedQuery(
        original_question="What recent trials exist for tuberculosis in pregnancy?",
        rewritten_question="What recent trials exist for tuberculosis in pregnancy?",
        recency_required=True,
    )
    assert nodes._primary_question_dimension(trials_query) == "trial_status"
