from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any
from xml.etree import ElementTree

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask

GENERIC_RETRIEVAL_TOKENS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "current",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "recent",
    "latest",
    "evidence",
    "evidence-based",
    "update",
    "updates",
    "find",
    "retrieve",
    "retrieving",
    "study",
    "studies",
    "article",
    "articles",
    "review",
    "reviews",
    "systematic",
    "meta",
    "meta-analysis",
    "analysis",
    "clinical",
    "trial",
    "trials",
    "guideline",
    "guidelines",
    "recommendation",
    "recommendations",
    "protocol",
    "protocols",
    "new",
    "of",
    "on",
    "or",
    "the",
    "to",
    "used",
    "using",
    "with",
    "without",
    "within",
    "years",
}


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


def _date_bounds(years: int) -> tuple[str, str]:
    start_year = max(datetime.now(UTC).year - max(years - 1, 0), 1900)
    return f"{start_year}/01/01", "3000"


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


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = _clean_term(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9/-]*", text.lower())


def _significant_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _tokenize(text):
        if len(token) < 3 or token in GENERIC_RETRIEVAL_TOKENS:
            continue
        tokens.append(token)
    return tokens


def _entity_terms(normalized_query: NormalizedQuery, task: SpecialistTask) -> tuple[list[str], set[str]]:
    if task.must_concepts or task.population_terms or task.intervention_terms:
        terms = _dedupe_preserve(task.must_concepts[:2] + task.population_terms[:2] + task.intervention_terms[:2])
        task_tokens = set()
        for text in task.must_concepts + task.population_terms + task.intervention_terms:
            task_tokens.update(_significant_tokens(text))
        return terms, task_tokens

    terms: list[str] = []
    entity_tokens: set[str] = set()
    seen_terms: set[str] = set()
    for entity in normalized_query.entities:
        normalized_text = _clean_term(entity.normalized_text)
        term_value = normalized_text
        if "population" in entity.category.lower() or "demographic" in (entity.role or "").lower():
            token_candidates = _significant_tokens(normalized_text)
            if len(token_candidates) > 1:
                term_value = token_candidates[0]
        if term_value and term_value.lower() not in seen_terms:
            terms.append(term_value)
            seen_terms.add(term_value.lower())
        entity_tokens.update(_significant_tokens(normalized_text))
    return terms, entity_tokens


def _focus_terms(task: SpecialistTask, entity_tokens: set[str], *, allow_multiword: bool = False) -> tuple[list[str], set[str]]:
    terms: list[str] = []
    focus_tokens: set[str] = set()
    seen_terms: set[str] = set()
    for focus_term in task.focus_terms:
        tokens = set(_significant_tokens(focus_term))
        if not tokens or tokens.issubset(entity_tokens):
            continue
        if not allow_multiword and len(tokens) != 1:
            continue
        cleaned = _clean_term(focus_term)
        if not cleaned or cleaned.lower() in seen_terms:
            continue
        terms.append(cleaned)
        seen_terms.add(cleaned.lower())
        focus_tokens.update(tokens)
    return terms, focus_tokens


def _purpose_terms(task: SpecialistTask, covered_tokens: set[str]) -> list[str]:
    purpose_tokens: list[str] = []
    seen: set[str] = set()
    for text in (task.query_text,):
        for token in _significant_tokens(text):
            if token in covered_tokens or token in seen:
                continue
            seen.add(token)
            purpose_tokens.append(token)
    if not purpose_tokens:
        for token in _significant_tokens(task.objective):
            if token in covered_tokens or token in seen:
                continue
            seen.add(token)
            purpose_tokens.append(token)
            break
    return purpose_tokens[:1]


def _build_structured_pubmed_term(normalized_query: NormalizedQuery, task: SpecialistTask) -> str:
    entity_terms, entity_tokens = _entity_terms(normalized_query, task)
    focus_terms: list[str] = []
    focus_tokens: set[str] = set()
    if task.question_focus_terms:
        focus_terms = _dedupe_preserve(task.question_focus_terms[:1])
        for term in focus_terms:
            focus_tokens.update(_significant_tokens(term))
    else:
        focus_terms, focus_tokens = _focus_terms(task, entity_tokens, allow_multiword=not entity_terms)
    purpose_terms = _purpose_terms(task, entity_tokens | focus_tokens)

    clauses: list[str] = []
    clauses.extend(entity_terms[:2])
    clauses.extend(focus_terms[:1])
    clauses.extend(purpose_terms)
    return " ".join(clause for clause in clauses if clause)


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

    title_text = raw_document.title.lower()
    abstract_text = (raw_document.abstract or "").lower()
    mesh_text = " ".join(raw_document.metadata.get("mesh_terms", [])).lower()
    text = " ".join(
        [
            title_text,
            abstract_text,
            " ".join(raw_document.metadata.get("pubtypes", [])),
            mesh_text,
        ]
    ).lower()

    ranking_terms = task.focus_terms or task.must_concepts or task.population_terms or task.intervention_terms
    for term in ranking_terms:
        if term.lower() in text:
            score += 7

    disease_tokens: set[str] = set()
    population_tokens: set[str] = set()
    if task.must_concepts or task.population_terms:
        for text_value in task.must_concepts:
            disease_tokens.update(_significant_tokens(text_value))
        for text_value in task.population_terms:
            population_tokens.update(_significant_tokens(text_value))
    else:
        for entity in normalized_query.entities:
            category = entity.category.lower()
            role = (entity.role or "").lower()
            tokens = set(_significant_tokens(entity.normalized_text))
            if "disease" in category or "condition" in category:
                disease_tokens.update(tokens)
            elif "population" in category or "demographic" in role:
                population_tokens.update(tokens)

    if disease_tokens:
        disease_title_or_mesh_hit = False
        for token in disease_tokens:
            if token in title_text:
                score += 12
                disease_title_or_mesh_hit = True
            elif token in mesh_text:
                score += 8
                disease_title_or_mesh_hit = True
            elif token in abstract_text:
                score += 3
        if not disease_title_or_mesh_hit:
            score -= 12

    for token in population_tokens:
        if token in title_text:
            score += 6
        elif token in mesh_text:
            score += 4
        elif token in abstract_text:
            score += 1

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
            "sort": "relevance",
            **self._common_params(),
        }
        if recency_required:
            mindate, maxdate = _date_bounds(self.settings.pubmed_recency_years)
            params.update(
                {
                    "datetype": "pdat",
                    "mindate": mindate,
                    "maxdate": maxdate,
                }
            )
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
                    _build_structured_pubmed_term(normalized_query, task),
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
