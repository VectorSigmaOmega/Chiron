from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.pubmed import PubMedConnector
from app.core.config import Settings
from app.schemas.common import ParsedQuery, SpecialistTask


def _mock_pubmed_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    if parsed.path.endswith("/esearch.fcgi"):
        assert query["db"] == ["pubmed"]
        return httpx.Response(
            200,
            json={
                "esearchresult": {
                    "idlist": ["40000001", "40000002"],
                }
            },
        )
    if parsed.path.endswith("/esummary.fcgi"):
        return httpx.Response(
            200,
            json={
                "result": {
                    "uids": ["40000001", "40000002"],
                    "40000001": {
                        "uid": "40000001",
                        "title": "Recent evidence for drug-resistant TB management",
                        "pubdate": "2026 Feb 21",
                        "fulljournalname": "Journal of Clinical Evidence",
                        "authors": [{"name": "Doe J"}],
                        "pubtype": ["Journal Article"],
                        "sortpubdate": "2026/02/21 00:00",
                    },
                    "40000002": {
                        "uid": "40000002",
                        "title": "Systematic review of pregnancy-specific TB safety data",
                        "pubdate": "2025 Nov",
                        "fulljournalname": "Review Journal",
                        "authors": [{"name": "Smith A"}],
                        "pubtype": ["Systematic Review"],
                        "sortpubdate": "2025/11/01 00:00",
                    },
                }
            },
        )
    raise AssertionError(f"Unexpected URL: {request.url}")


async def test_pubmed_connector_returns_normalized_documents() -> None:
    connector = PubMedConnector(
        settings=Settings(
            literature_connector_mode="pubmed",
            pubmed_base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        ),
        transport=httpx.MockTransport(_mock_pubmed_transport),
    )
    parsed_query = ParsedQuery(
        original_question="Latest treatment for drug-resistant TB in pregnancy",
        rewritten_question="Latest treatment for drug-resistant TB in pregnancy",
        recency_required=True,
    )
    task = SpecialistTask(
        task_id="task-1",
        agent_type="literature",
        goal="Search literature",
        subquery=parsed_query.rewritten_question,
        depends_on=[],
        focus_entities=["drug-resistant tuberculosis"],
    )

    documents = await connector.search(parsed_query, task)

    assert len(documents) == 2
    assert documents[0].source_id == "40000001"
    assert documents[0].source_type == "study"
    assert documents[0].title == "Recent evidence for drug-resistant TB management"
    assert documents[1].source_type == "review"
    assert documents[1].publication_date is not None
