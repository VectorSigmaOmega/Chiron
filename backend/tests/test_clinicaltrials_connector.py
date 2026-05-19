from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.clinicaltrials import ClinicalTrialsConnector
from app.core.config import Settings
from app.schemas.common import NormalizedQuery, ScopeDecision, SpecialistTask


def _mock_trials_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    assert parsed.path.endswith("/studies")
    assert query["pageSize"] == ["3"]
    assert query["query.term"] == ["drug-resistant tuberculosis pregnancy regimen"]
    return httpx.Response(
        200,
        json={
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT99999999",
                            "briefTitle": "Drug-resistant TB pregnancy regimen study",
                        },
                        "statusModule": {
                            "overallStatus": "RECRUITING",
                            "lastUpdatePostDateStruct": {"date": "2026-03-12", "type": "ACTUAL"},
                        },
                        "descriptionModule": {
                            "briefSummary": "A study evaluating drug-resistant TB treatment options in pregnancy.",
                        },
                        "conditionsModule": {"conditions": ["Drug-Resistant Tuberculosis"]},
                        "eligibilityModule": {
                            "sex": "FEMALE",
                            "stdAges": ["ADULT"],
                            "eligibilityCriteria": "Inclusion Criteria: Pregnant adults with drug-resistant TB. Exclusion Criteria: Severe liver failure."
                        },
                        "armsInterventionsModule": {
                            "interventions": [{"name": "Bedaquiline-containing regimen"}]
                        },
                        "designModule": {"phases": ["PHASE3"]},
                    }
                }
            ]
        },
    )


async def test_clinicaltrials_connector_returns_normalized_documents() -> None:
    connector = ClinicalTrialsConnector(
        settings=Settings(trials_connector_mode="clinicaltrials"),
        transport=httpx.MockTransport(_mock_trials_transport),
    )
    normalized_query = NormalizedQuery(
        raw_question="Latest trials for drug-resistant tuberculosis in pregnancy",
        normalized_question="Recent trials for drug-resistant tuberculosis in pregnancy",
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
        recency_focus=True,
    )
    task = SpecialistTask(
        task_id="task-ct",
        agent_type="trials",
        objective="Search trial registry",
        query_text=normalized_query.normalized_question,
        source_query="drug-resistant tuberculosis pregnancy regimen",
        focus_terms=["drug-resistant tuberculosis", "pregnancy"],
    )
    documents = await connector.search(normalized_query, task)
    assert len(documents) == 1
    assert documents[0].source_id == "NCT99999999"
    assert documents[0].source_type == "registry"
    assert documents[0].metadata["overall_status"] == "Recruiting"
    assert documents[0].metadata["phase"] == ["Phase 3"]
    assert documents[0].metadata["candidate_drugs"] == ["Bedaquiline-containing regimen"]
    assert "Pregnant adults" in (documents[0].metadata["population"] or "")
    assert "Eligibility excerpt:" in (documents[0].abstract or "")
