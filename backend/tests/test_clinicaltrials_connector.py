from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.clinicaltrials import ClinicalTrialsConnector
from app.core.config import Settings
from app.schemas.common import ParsedQuery, SpecialistTask


def _mock_trials_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    assert parsed.path.endswith("/studies")
    assert query["pageSize"] == ["3"]
    assert query["query.cond"] == ["drug-resistant tuberculosis"]
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
    parsed_query = ParsedQuery(
        original_question="Latest trials for drug-resistant tuberculosis in pregnancy",
        rewritten_question="Latest trials for drug-resistant tuberculosis in pregnancy",
        recency_required=True,
    )
    task = SpecialistTask(
        task_id="task-ct",
        agent_type="trials",
        goal="Search trial registry",
        subquery=parsed_query.rewritten_question,
        depends_on=[],
        focus_entities=["drug-resistant tuberculosis"],
    )
    documents = await connector.search(parsed_query, task)
    assert len(documents) == 1
    assert documents[0].source_id == "NCT99999999"
    assert documents[0].source_type == "registry"
    assert documents[0].metadata["overall_status"] == "RECRUITING"
