from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.dailymed import DailyMedConnector
from app.core.config import Settings
from app.schemas.common import NormalizedQuery, QueryEntity, ScopeDecision, SpecialistTask


def _mock_dailymed_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    if parsed.path.endswith("/spls.json"):
        assert query["drug_name"] == ["bedaquiline"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "spl_version": 33,
                        "published_date": "Nov 17, 2025",
                        "title": "SIRTURO (BEDAQUILINE FUMARATE) TABLET",
                        "setid": "1534c9ae-4948-4cf4-9f66-222a99db6d0e",
                    }
                ]
            },
        )
    if parsed.path.endswith("/spls/1534c9ae-4948-4cf4-9f66-222a99db6d0e.xml"):
        return httpx.Response(
            200,
            text="""
            <document xmlns="urn:hl7-org:v3">
              <title>SIRTURO</title>
              <section>
                <title>Warnings and Precautions</title>
                <text>Warning: QT prolongation and hepatotoxicity are important safety considerations.</text>
              </section>
              <section>
                <title>Contraindications</title>
                <text>Contraindications include known hypersensitivity.</text>
              </section>
            </document>
            """,
        )
    raise AssertionError(f"Unexpected URL: {request.url}")


async def test_dailymed_connector_returns_label_document() -> None:
    connector = DailyMedConnector(
        settings=Settings(drug_safety_connector_mode="dailymed"),
        transport=httpx.MockTransport(_mock_dailymed_transport),
    )
    normalized_query = NormalizedQuery(
        raw_question="Major safety concerns with bedaquiline",
        normalized_question="Major safety concerns with bedaquiline",
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
        entities=[QueryEntity(text="bedaquiline", normalized_text="bedaquiline", category="drug", role="primary")],
    )
    task = SpecialistTask(
        task_id="task-dm",
        agent_type="drug_safety",
        objective="Lookup safety concerns",
        query_text=normalized_query.normalized_question,
        source_query="bedaquiline",
        focus_terms=["bedaquiline"],
    )
    documents = await connector.search(normalized_query, task)
    assert len(documents) == 1
    assert documents[0].source_type == "label"
    assert "qt prolongation" in (documents[0].abstract or "").lower()
    assert "Contraindications:" in (documents[0].abstract or "")
    assert documents[0].metadata["contraindications_excerpt"] is not None
