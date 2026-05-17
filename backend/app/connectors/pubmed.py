from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import ParsedQuery, SourceDocument, SpecialistTask


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

    async def search(self, parsed_query: ParsedQuery, task: SpecialistTask) -> list[SourceDocument]:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(
            base_url=self.settings.pubmed_base_url,
            timeout=timeout,
            transport=self.transport,
        ) as client:
            ids = await self._esearch(client, task.subquery or parsed_query.rewritten_question, parsed_query.recency_required)
            if not ids:
                return []
            summary = await self._esummary(client, ids)

        documents: list[SourceDocument] = []
        for pmid in summary.get("uids", []):
            raw = summary.get(pmid)
            if not raw:
                continue
            pubtypes = list(raw.get("pubtype", []))
            source_type = _classify_pubmed_source(pubtypes)
            if any("preprint" in pubtype.lower() for pubtype in pubtypes):
                continue
            documents.append(
                SourceDocument(
                    source_id=pmid,
                    source_type=source_type,
                    title=raw.get("title") or f"PubMed article {pmid}",
                    url=_pubmed_article_url(pmid),
                    publication_date=_parse_pubmed_date(raw.get("pubdate")),
                    publisher=raw.get("fulljournalname") or "PubMed",
                    abstract=None,
                    full_text=None,
                    metadata={
                        "authors": [author.get("name") for author in raw.get("authors", []) if author.get("name")],
                        "journal": raw.get("fulljournalname"),
                        "pubtypes": pubtypes,
                        "sortpubdate": raw.get("sortpubdate"),
                    },
                )
            )
        return documents
