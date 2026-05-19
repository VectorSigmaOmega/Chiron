from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.guidelines import ECRIGuidelineConnector
from app.core.config import Settings
from app.schemas.common import NormalizedQuery, ScopeDecision, SpecialistTask


def _mock_ecri_html_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    if parsed.netloc == "guidelines.ecri.org" and parsed.path == "/api/public/briefs":
        assert query["q"] == ["tuberculosis pregnancy"]
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "uniqueId": 501,
                        "guidelineTitle": "Tuberculosis management in pregnancy guideline",
                        "publicationYear": "2025",
                        "publicationReaffirmationDate": "2025 Jan 14",
                        "organizations": [{"title": "Example Health Authority"}],
                        "accessTheGuideline": "https://example.org/tb-pregnancy-guideline",
                        "isGuidelineHaveQuality": True,
                        "isGuidelineRateQuality": True,
                        "source": (
                            "Example Health Authority. Tuberculosis management in pregnancy guideline. "
                            "[GUIDELINE PROFILE & TRUST SCORECARD](https://cdn.example.org/scorecard-501.pdf)"
                        ),
                    },
                    {
                        "uniqueId": 999,
                        "guidelineTitle": "COVID-19 vaccination recommendations",
                        "publicationYear": "2025",
                        "organizations": [{"title": "Another Org"}],
                        "accessTheGuideline": "https://example.org/covid-guideline",
                        "source": "Another Org. COVID-19 vaccination recommendations.",
                    },
                ]
            },
        )
    if parsed.netloc == "example.org" and parsed.path == "/tb-pregnancy-guideline":
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text="""
            <html><body>
              <main>
                <h1>Tuberculosis management in pregnancy guideline</h1>
                <p>Pregnant patients with active tuberculosis should receive prompt treatment using established multidrug regimens.</p>
                <p>Clinical review should include assessment of maternal disease severity and fetal considerations.</p>
                <p>Drug-resistant tuberculosis requires specialist input and individualized regimen selection.</p>
              </main>
            </body></html>
            """,
        )
    if parsed.netloc == "example.org" and parsed.path == "/covid-guideline":
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><body><p>COVID guideline</p></body></html>",
        )
    raise AssertionError(f"Unexpected URL: {request.url}")


def _mock_ecri_inaccessible_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    if parsed.netloc == "guidelines.ecri.org" and parsed.path == "/api/public/briefs":
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "uniqueId": 601,
                        "guidelineTitle": "Tuberculosis treatment guideline",
                        "publicationYear": "2024",
                        "organizations": [{"title": "World Health Organization (WHO)"}],
                        "accessTheGuideline": "https://example.org/inaccessible-guideline.pdf",
                        "source": (
                            "World Health Organization (WHO). Tuberculosis treatment guideline. "
                            "[GUIDELINE PROFILE & TRUST SCORECARD](https://cdn.example.org/scorecard-601.pdf)"
                        ),
                    }
                ]
            },
        )
    if parsed.netloc == "example.org" and parsed.path == "/inaccessible-guideline.pdf":
        return httpx.Response(403, headers={"Content-Type": "text/html"}, text="forbidden")
    raise AssertionError(f"Unexpected URL: {request.url}")


async def test_ecri_connector_returns_accessible_guideline_documents() -> None:
    connector = ECRIGuidelineConnector(
        settings=Settings(guideline_connector_mode="ecri", ecri_base_url="https://guidelines.ecri.org"),
        transport=httpx.MockTransport(_mock_ecri_html_transport),
    )
    normalized_query = NormalizedQuery(
        raw_question="latest treatment for TB in pregnant women",
        normalized_question="What is the latest treatment for tuberculosis in pregnant women?",
        intent_summary="Retrieve current treatment guidance for tuberculosis in pregnancy.",
        scope=ScopeDecision(in_scope=True),
    )
    task = SpecialistTask(
        task_id="guideline-task",
        agent_type="guideline",
        objective="Discover accessible guidelines for tuberculosis treatment in pregnancy.",
        query_text=normalized_query.normalized_question,
        must_concepts=["tuberculosis"],
        population_terms=["pregnancy"],
        question_focus_terms=["treatment guidance"],
        desired_result_count=2,
    )

    documents = await connector.search(normalized_query, task)

    assert len(documents) == 1
    document = documents[0]
    assert document.source_type == "guideline"
    assert document.publisher == "Example Health Authority"
    assert document.metadata["source_mode"] == "ecri"
    assert document.metadata["access_status"] == "accessible"
    assert document.metadata["trust_scorecard_url"] == "https://cdn.example.org/scorecard-501.pdf"
    assert document.abstract is not None
    assert "tuberculosis" in document.abstract.lower()
    assert "pregnant" in document.abstract.lower()


async def test_ecri_connector_returns_candidate_when_original_document_inaccessible() -> None:
    connector = ECRIGuidelineConnector(
        settings=Settings(guideline_connector_mode="ecri", ecri_base_url="https://guidelines.ecri.org"),
        transport=httpx.MockTransport(_mock_ecri_inaccessible_transport),
    )
    normalized_query = NormalizedQuery(
        raw_question="tuberculosis treatment guideline",
        normalized_question="Current tuberculosis treatment guideline",
        intent_summary="Locate current tuberculosis treatment guidance.",
        scope=ScopeDecision(in_scope=True),
    )
    task = SpecialistTask(
        task_id="guideline-task",
        agent_type="guideline",
        objective="Discover accessible guidelines for tuberculosis treatment.",
        query_text=normalized_query.normalized_question,
        must_concepts=["tuberculosis"],
        question_focus_terms=["treatment guidance"],
    )

    documents = await connector.search(normalized_query, task)

    assert len(documents) == 1
    document = documents[0]
    assert document.source_type == "guideline_candidate"
    assert document.metadata["access_status"] == "http_403"
    assert "not accessible" in (document.abstract or "").lower()
