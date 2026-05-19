from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.pubmed import PubMedConnector
from app.core.config import Settings
from app.schemas.common import NormalizedQuery, ScopeDecision, SpecialistTask


def _mock_pubmed_transport(request: httpx.Request) -> httpx.Response:
    parsed = urlparse(str(request.url))
    query = parse_qs(parsed.query)
    if parsed.path.endswith("/esearch.fcgi"):
        assert query["db"] == ["pubmed"]
        term = query["term"][0].lower()
        assert "drug-resistant tuberculosis" in term
        assert query["sort"] == ["relevance"]
        assert query["datetype"] == ["pdat"]
        assert "last 5 years" not in term
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
    if parsed.path.endswith("/efetch.fcgi"):
        return httpx.Response(
            200,
            text="""
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40000001</PMID>
      <Article>
        <Abstract>
          <AbstractText>Observational evidence suggests individualized treatment regimens remain necessary in pregnancy.</AbstractText>
        </Abstract>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Pregnancy</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>40000002</PMID>
      <Article>
        <Abstract>
          <AbstractText>Systematic review evidence summarizes pregnancy-specific safety data for multidrug-resistant tuberculosis therapy.</AbstractText>
        </Abstract>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Tuberculosis, Multidrug-Resistant</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
            """.strip(),
            headers={"Content-Type": "application/xml"},
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
    normalized_query = NormalizedQuery(
        raw_question="Latest treatment for drug-resistant TB in pregnancy",
        normalized_question="Current evidence-based treatment for drug-resistant tuberculosis in pregnancy",
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
        recency_focus=True,
    )
    task = SpecialistTask(
        task_id="task-1",
        agent_type="literature",
        objective="Search literature",
        query_text=normalized_query.normalized_question,
        source_query="drug-resistant tuberculosis AND pregnancy AND treatment",
        focus_terms=["drug-resistant tuberculosis", "pregnancy"],
    )

    documents = await connector.search(normalized_query, task)

    assert len(documents) == 1
    assert documents[0].source_id == "40000002"
    assert documents[0].source_type == "review"
    assert documents[0].abstract is not None
    assert "pregnancy-specific safety data" in documents[0].abstract
    assert documents[0].publication_date is not None


async def test_pubmed_connector_uses_llm_generated_source_query() -> None:
    seen_terms: list[str] = []
    seen_params: list[dict[str, list[str]]] = []

    def _mock_pubmed_hiv_transport(request: httpx.Request) -> httpx.Response:
        parsed = urlparse(str(request.url))
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/esearch.fcgi"):
            seen_terms.append(query["term"][0].lower())
            seen_params.append(query)
            return httpx.Response(200, json={"esearchresult": {"idlist": []}})
        if parsed.path.endswith("/esummary.fcgi"):
            return httpx.Response(200, json={"result": {"uids": []}})
        if parsed.path.endswith("/efetch.fcgi"):
            return httpx.Response(200, text="<PubmedArticleSet />")
        raise AssertionError(f"Unexpected URL: {request.url}")

    connector = PubMedConnector(
        settings=Settings(
            literature_connector_mode="pubmed",
            pubmed_base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        ),
        transport=httpx.MockTransport(_mock_pubmed_hiv_transport),
    )
    normalized_query = NormalizedQuery(
        raw_question="Latest TB treatment in patients with HIV",
        normalized_question="Current treatment for tuberculosis in patients with HIV",
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
        recency_focus=True,
    )
    task = SpecialistTask(
        task_id="task-hiv",
        agent_type="literature",
        objective="Search literature",
        query_text=normalized_query.normalized_question,
        source_query="tuberculosis AND HIV AND treatment",
        focus_terms=["tuberculosis", "HIV"],
    )

    documents = await connector.search(normalized_query, task)

    assert documents == []
    assert any("hiv" in term and "tuberculosis" in term for term in seen_terms)
    assert any(params.get("datetype") == ["pdat"] for params in seen_params)
    assert all("last 5 years" not in term for term in seen_terms)


async def test_pubmed_connector_compiles_structured_query_and_date_filters() -> None:
    seen_params: list[dict[str, list[str]]] = []

    def _mock_pubmed_tb_pregnancy_transport(request: httpx.Request) -> httpx.Response:
        parsed = urlparse(str(request.url))
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/esearch.fcgi"):
            seen_params.append(query)
            return httpx.Response(200, json={"esearchresult": {"idlist": []}})
        if parsed.path.endswith("/esummary.fcgi"):
            return httpx.Response(200, json={"result": {"uids": []}})
        if parsed.path.endswith("/efetch.fcgi"):
            return httpx.Response(200, text="<PubmedArticleSet />")
        raise AssertionError(f"Unexpected URL: {request.url}")

    connector = PubMedConnector(
        settings=Settings(
            literature_connector_mode="pubmed",
            pubmed_base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        ),
        transport=httpx.MockTransport(_mock_pubmed_tb_pregnancy_transport),
    )
    normalized_query = NormalizedQuery(
        raw_question="latest treatment for TB in pregnant women",
        normalized_question="What is the latest treatment for tuberculosis in pregnant women?",
        intent_summary="Seeking current evidence-based treatment protocols for tuberculosis in pregnancy.",
        scope=ScopeDecision(in_scope=True),
        recency_focus=True,
        entities=[
            {"text": "TB", "normalized_text": "tuberculosis", "category": "disease", "role": "primary condition", "salience": "high"},
            {"text": "pregnant women", "normalized_text": "pregnant women", "category": "population", "role": "patient demographic", "salience": "high"},
        ],
    )
    task = SpecialistTask(
        task_id="task-tb-pregnancy",
        agent_type="literature",
        objective="Find recent systematic reviews and clinical studies on TB treatment outcomes and new regimens in pregnancy.",
        query_text="recent evidence and updates for tuberculosis treatment in pregnant women",
        source_query="tuberculosis treatment pregnancy AND (systematic review OR meta-analysis OR clinical trial) AND last 5 years",
        focus_terms=["tuberculosis", "pregnancy", "treatment outcomes", "recent evidence"],
    )

    documents = await connector.search(normalized_query, task)

    assert documents == []
    assert seen_params
    first = seen_params[0]
    term = first["term"][0].lower()
    assert "tuberculosis" in term
    assert "pregnant" in term
    assert "pregnancy" in term
    assert "treatment" in term
    assert "last 5 years" not in term
    assert first["sort"] == ["relevance"]
    assert first["datetype"] == ["pdat"]
    assert first["mindate"] == ["2022/01/01"]
    assert first["maxdate"] == ["3000"]
