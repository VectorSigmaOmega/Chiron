from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from xml.etree import ElementTree

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask


def _parse_pubmed_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    parts = text.split()
    try:
        year = int(parts[0])
    except (ValueError, IndexError):
        return None
    month_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    month = 1
    day = 1
    if len(parts) >= 2:
        month = month_map.get(parts[1][:3], 1)
    if len(parts) >= 3:
        try:
            day = int(parts[2])
        except ValueError:
            day = 1
    return date(year, month, day)


def _classify_pubmed_source(pubtypes: list[str]) -> str:
    lowered = {pubtype.lower() for pubtype in pubtypes}
    if "practice guideline" in lowered or "guideline" in lowered:
        return "guideline"
    if "systematic review" in lowered or "meta-analysis" in lowered or "review" in lowered:
        return "review"
    return "study"


def _pubmed_article_url(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _clean_term(term: str) -> str:
    return term.strip().rstrip("?")


def _date_filter(years: int) -> str:
    start_year = max(datetime.now(UTC).year - max(years - 1, 0), 1900)
    return f'("{start_year}/01/01"[Date - Publication] : "3000"[Date - Publication])'


def _unique_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        cleaned = term.strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _build_pubmed_term(task: SpecialistTask, *, years: int, recency_focus: bool) -> str:
    clauses: list[str] = []
    source_query = _clean_term(task.source_query or task.query_text)
    if source_query:
        clauses.append(source_query)
    if recency_focus:
        clauses.append(_date_filter(years))
    return " AND ".join(clauses) if clauses else ""


def _rank_document(
    raw_document: SourceDocument,
    *,
    normalized_query: NormalizedQuery,
    task: SpecialistTask,
) -> tuple[int, float]:
    score = 0
    source_priority = {"guideline": 4, "review": 3, "label": 3, "study": 2, "registry": 1}.get(
        raw_document.source_type, 1
    )
    score += source_priority * 10

    text = " ".join(
        [
            raw_document.title,
            raw_document.abstract or "",
            " ".join(raw_document.metadata.get("pubtypes", [])),
            " ".join(raw_document.metadata.get("mesh_terms", [])),
        ]
    ).lower()

    for term in task.focus_terms:
        if term.lower() in text:
            score += 7

    publication_date = raw_document.publication_date or date(1900, 1, 1)
    freshness = publication_date.toordinal() / 10000
    return score, freshness


def _parse_pubmed_abstracts(xml_text: str) -> dict[str, dict[str, Any]]:
    root = ElementTree.fromstring(xml_text)
    records: dict[str, dict[str, Any]] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//MedlineCitation/PMID")
        if not pmid:
            continue
        abstract_parts = []
        for node in article.findall(".//Abstract/AbstractText"):
            label = node.attrib.get("Label")
            text = "".join(node.itertext()).strip()
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)
        mesh_terms = [
            "".join(node.itertext()).strip()
            for node in article.findall(".//MeshHeading/DescriptorName")
            if "".join(node.itertext()).strip()
        ]
        records[pmid] = {
            "abstract": " ".join(abstract_parts).strip() or None,
            "mesh_terms": mesh_terms,
        }
    return records


class PubMedConnector(BaseConnector):
    connector_name = "pubmed"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def _common_params(self) -> dict[str, str]:
        params = {"tool": self.settings.pubmed_tool}
        if self.settings.pubmed_api_key:
            params["api_key"] = self.settings.pubmed_api_key
        if self.settings.pubmed_email:
            params["email"] = self.settings.pubmed_email
        return params

    async def _esearch(self, client: httpx.AsyncClient, term: str, recency_required: bool) -> list[str]:
        params = {
            "db": "pubmed",
            "term": _clean_term(term),
            "retmode": "json",
            "retmax": str(self.settings.pubmed_retmax),
            "sort": "pub_date" if recency_required else "relevance",
            **self._common_params(),
        }
        response = await client.get("/esearch.fcgi", params=params)
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("esearchresult", {}).get("idlist", []))

    async def _esummary(self, client: httpx.AsyncClient, ids: list[str]) -> dict[str, Any]:
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            **self._common_params(),
        }
        response = await client.get("/esummary.fcgi", params=params)
        response.raise_for_status()
        return response.json().get("result", {})

    async def _efetch(self, client: httpx.AsyncClient, ids: list[str]) -> dict[str, dict[str, Any]]:
        params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            **self._common_params(),
        }
        response = await client.get("/efetch.fcgi", params=params)
        response.raise_for_status()
        return _parse_pubmed_abstracts(response.text)

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(
            base_url=self.settings.pubmed_base_url,
            timeout=timeout,
            transport=self.transport,
        ) as client:
            search_terms = _unique_terms(
                [
                    _build_pubmed_term(task, years=self.settings.pubmed_recency_years, recency_focus=normalized_query.recency_focus),
                    task.query_text,
                    normalized_query.normalized_question,
                    normalized_query.raw_question,
                ]
            )
            ids: list[str] = []
            for term in search_terms:
                ids = await self._esearch(client, term, normalized_query.recency_focus)
                if ids:
                    break
            if not ids:
                return []
            summary = await self._esummary(client, ids)
            abstract_map = await self._efetch(client, ids)

        documents: list[SourceDocument] = []
        for pmid in summary.get("uids", []):
            raw = summary.get(pmid)
            if not raw:
                continue
            pubtypes = list(raw.get("pubtype", []))
            source_type = _classify_pubmed_source(pubtypes)
            if any("preprint" in pubtype.lower() for pubtype in pubtypes):
                continue
            abstract_info = abstract_map.get(pmid, {})
            documents.append(
                SourceDocument(
                    source_id=pmid,
                    source_type=source_type,
                    title=raw.get("title") or f"PubMed article {pmid}",
                    url=_pubmed_article_url(pmid),
                    publication_date=_parse_pubmed_date(raw.get("pubdate")),
                    publisher=raw.get("fulljournalname") or "PubMed",
                    abstract=abstract_info.get("abstract"),
                    full_text=None,
                    metadata={
                        "authors": [author.get("name") for author in raw.get("authors", []) if author.get("name")],
                        "journal": raw.get("fulljournalname"),
                        "pubtypes": pubtypes,
                        "sortpubdate": raw.get("sortpubdate"),
                        "mesh_terms": abstract_info.get("mesh_terms", []),
                    },
                )
            )
        scored_documents = [
            (_rank_document(document, normalized_query=normalized_query, task=task), document)
            for document in documents
        ]
        scored_documents.sort(key=lambda item: item[0], reverse=True)
        if not scored_documents:
            return []
        score_floor = max(scored_documents[0][0][0] - 12, 10)
        filtered = [document for (score, _freshness), document in scored_documents if score >= score_floor]
        return filtered[: self.settings.pubmed_retmax]
