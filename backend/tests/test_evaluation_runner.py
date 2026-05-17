from app.evaluation.runner import BenchmarkCase, compare_case
from app.schemas.common import AssistantResponse, Citation, EvidenceItem


def test_compare_case_passes_when_response_matches_expectations() -> None:
    case = BenchmarkCase(
        case_id="answered_case",
        question="Latest treatment for condition X",
        expected_status="answered",
        expected_substrings=["specialist consultation"],
        expected_min_citations=1,
        expected_min_evidence_items=1,
    )
    response = AssistantResponse(
        status="answered",
        answer="Current management requires specialist consultation.",
        evidence_summary=[],
        citations=[
            Citation(
                label="1",
                source_id="src1",
                title="Source 1",
                url="https://example.com",
            )
        ],
        evidence_items=[
            EvidenceItem(
                evidence_id="ev1",
                source_id="src1",
                source_type="guideline",
                title="Source 1",
                url="https://example.com",
                key_claim="Current management requires specialist consultation.",
            )
        ],
    )

    result = compare_case(case, response)

    assert result.passed is True
    assert result.notes == []


def test_compare_case_fails_on_status_and_missing_substrings() -> None:
    case = BenchmarkCase(
        case_id="clarify_case",
        question="Best treatment for pneumonia?",
        expected_status="needs_clarification",
        expected_substrings=["care setting"],
    )
    response = AssistantResponse(
        status="answered",
        answer="A generic answer with no clarifying question.",
        evidence_summary=[],
    )

    result = compare_case(case, response)

    assert result.passed is False
    assert result.actual_status == "answered"
    assert "care setting" in result.missing_substrings
