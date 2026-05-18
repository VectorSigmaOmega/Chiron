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
        term = query["term"][0].lower()
        assert "pregnancy" in term
        assert "treatment" in term
        assert "drug-resistant tuberculosis" in term or "multidrug-resistant tuberculosis" in term
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

    assert len(documents) == 1
    assert documents[0].source_id == "40000002"
    assert documents[0].source_type == "review"
    assert documents[0].abstract is not None
    assert "pregnancy-specific safety data" in documents[0].abstract
    assert documents[0].publication_date is not None


async def test_pubmed_connector_includes_general_clinical_modifiers_in_query() -> None:
    seen_terms: list[str] = []

    def _mock_pubmed_hiv_transport(request: httpx.Request) -> httpx.Response:
        parsed = urlparse(str(request.url))
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/esearch.fcgi"):
            seen_terms.append(query["term"][0].lower())
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
    parsed_query = ParsedQuery(
        original_question="Latest TB treatment in patients with HIV",
        rewritten_question="Latest TB treatment in patients with HIV",
        recency_required=True,
        clinical_modifiers=["hiv"],
        comorbidities=["hiv"],
        entities=[],
    )
    task = SpecialistTask(
        task_id="task-hiv",
        agent_type="literature",
        goal="Search literature",
        subquery=parsed_query.rewritten_question,
        depends_on=[],
        focus_entities=["tuberculosis"],
    )

    documents = await connector.search(parsed_query, task)

    assert documents == []
    assert any("hiv" in term and "tuberculosis" in term for term in seen_terms)
