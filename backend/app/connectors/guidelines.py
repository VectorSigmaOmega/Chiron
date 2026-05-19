from __future__ import annotations

import json
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask

WHITESPACE_RE = re.compile(r"\s+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^) ]+)(?: [^)]+)?\)")


def _collapse_whitespace(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _extract_markdown_link(source_text: str, label: str) -> str | None:
    for match in MARKDOWN_LINK_RE.finditer(source_text or ""):
        if match.group(1).strip().lower() == label.lower():
            return match.group(2).strip()
    return None


def _parse_publication_date(value: str | None, year_value: str | None = None) -> date | None:
    if value:
        text = value.strip()
        if text:
            year_match = re.search(r"\b(\d{4})\b", text)
            if year_match:
                year = int(year_match.group(1))
                month = 1
                day = 1
                month_map = {
                    "jan": 1,
                    "feb": 2,
                    "mar": 3,
                    "apr": 4,
                    "may": 5,
                    "jun": 6,
                    "jul": 7,
                    "aug": 8,
                    "sep": 9,
                    "oct": 10,
                    "nov": 11,
                    "dec": 12,
                }
                for token, token_month in month_map.items():
                    if token in text.lower():
                        month = token_month
                        break
                day_match = re.search(r"\b(\d{1,2})\b", text.split(str(year), 1)[-1])
                if day_match:
                    day = int(day_match.group(1))
                return date(year, month, day)
    if year_value and year_value.isdigit():
        return date(int(year_value), 1, 1)
    return None


def _significant_tokens(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9][a-z0-9/-]*", value.lower()):
            if len(token) < 3:
                continue
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
    return ordered


def _compile_ecri_query(normalized_query: NormalizedQuery, task: SpecialistTask) -> str:
    query_terms = [
        *task.must_concepts[:3],
        *task.population_terms[:2],
        *task.intervention_terms[:2],
    ]
    if not query_terms:
        query_terms = [entity.normalized_text for entity in normalized_query.entities[:4]]
    if not query_terms:
        query_terms = [normalized_query.normalized_question]
    deduped: list[str] = []
    seen: set[str] = set()
    for term in query_terms:
        cleaned = _collapse_whitespace(term)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return " ".join(deduped[:5])


def _rank_ecri_hit(hit: dict, task: SpecialistTask) -> tuple[int, int]:
    title = (hit.get("guidelineTitle") or "").lower()
    source = (hit.get("source") or "").lower()
    combined = f"{title} {source}"
    must_tokens = _significant_tokens(task.must_concepts)
    population_tokens = _significant_tokens(task.population_terms)
    intervention_tokens = _significant_tokens(task.intervention_terms)
    focus_tokens = _significant_tokens(task.question_focus_terms)
    exclude_tokens = set(_significant_tokens(task.exclude_concepts))

    score = 0
    for token in must_tokens:
        if token in title:
            score += 10
        elif token in combined:
            score += 4
    for token in population_tokens:
        if token in title:
            score += 6
        elif token in combined:
            score += 3
    for token in intervention_tokens:
        if token in title:
            score += 6
        elif token in combined:
            score += 3
    for token in focus_tokens:
        if token in title:
            score += 2
        elif token in combined:
            score += 1
    for token in exclude_tokens:
        if token in combined:
            score -= 8
    if hit.get("isGuidelineRateQuality"):
        score += 4
    if hit.get("isGuidelineHaveQuality"):
        score += 2
    publication_date = _parse_publication_date(hit.get("publicationReaffirmationDate"), hit.get("publicationYear"))
    freshness = publication_date.toordinal() if publication_date else 0
    return score, freshness


def _extract_pdf_text(content: bytes, *, max_pages: int, max_chars: int) -> str | None:
    try:
        reader = PdfReader(BytesIO(content))
    except Exception:
        return None
    chunks: list[str] = []
    remaining_chars = max_chars
    for page in reader.pages[:max_pages]:
        if remaining_chars <= 0:
            break
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = _collapse_whitespace(text)
        if not cleaned:
            continue
        chunks.append(cleaned[:remaining_chars])
        remaining_chars -= len(chunks[-1])
    combined = "\n".join(chunks).strip()
    return combined or None


def _extract_html_text(content: str, *, max_chars: int) -> str | None:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg"]):
        tag.decompose()
    text = _collapse_whitespace(soup.get_text("\n"))
    return text[:max_chars] if text else None


def _select_relevant_excerpt(text: str | None, task: SpecialistTask, *, max_chars: int = 1800) -> str | None:
    if not text:
        return None
    paragraphs = [
        _collapse_whitespace(paragraph)
        for paragraph in re.split(r"\n{2,}|(?<=[.!?])\s{2,}", text)
        if _collapse_whitespace(paragraph)
    ]
    if not paragraphs:
        cleaned = _collapse_whitespace(text)
        return cleaned[:max_chars] if cleaned else None

    query_tokens = _significant_tokens(
        [
            *task.must_concepts,
            *task.population_terms,
            *task.intervention_terms,
            *task.question_focus_terms,
            task.query_text,
        ]
    )
    ranked: list[tuple[int, str]] = []
    for paragraph in paragraphs:
        lowered = paragraph.lower()
        score = sum(1 for token in query_tokens if token in lowered)
        if score == 0 and len(paragraph) < 80:
            continue
        ranked.append((score, paragraph))
    ranked.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    selected = [paragraph for _, paragraph in ranked[:3]] or paragraphs[:2]
    excerpt = " ".join(selected)
    excerpt = _collapse_whitespace(excerpt)
    return excerpt[:max_chars] if excerpt else None


class GuidelineFixtureConnector(BaseConnector):
    connector_name = "guideline_fixture"

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._records = self._load_records(self.settings.guideline_fixture_path)

    @staticmethod
    def _load_records(path: str) -> list[dict]:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return list(payload.get("guidelines", []))

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        structured_terms = [
            *task.must_concepts,
            *task.population_terms,
            *task.intervention_terms,
            *task.question_focus_terms,
            *task.supporting_concepts,
        ]
        haystack = " ".join(
            [
                normalized_query.raw_question,
                normalized_query.normalized_question,
                task.query_text,
                task.source_query or "",
                *task.focus_terms,
                *structured_terms,
            ]
        ).lower()
        ranked_documents: list[tuple[int, SourceDocument]] = []
        for record in self._records:
            keywords = [keyword.lower() for keyword in record.get("keywords", [])]
            required_keywords = [keyword.lower() for keyword in record.get("required_keywords", [])]
            if required_keywords and not all(keyword in haystack for keyword in required_keywords):
                continue
            overlap = sum(1 for keyword in keywords if keyword in haystack)
            if keywords and overlap == 0:
                continue
            publication_date = None
            if record.get("publication_date"):
                publication_date = date.fromisoformat(record["publication_date"])
            ranked_documents.append(
                (
                    overlap,
                    SourceDocument(
                        source_id=record["source_id"],
                        source_type="guideline",
                        title=record["title"],
                        url=record["url"],
                        publication_date=publication_date,
                        publisher=record.get("publisher"),
                        abstract=record.get("summary"),
                        full_text=None,
                        metadata={
                            "condition": record.get("condition"),
                            "population": record.get("population"),
                            "source_mode": "fixture",
                            "access_status": "accessible",
                        },
                    ),
                )
            )
        ranked_documents.sort(
            key=lambda item: (
                item[0],
                item[1].publication_date.toordinal() if item[1].publication_date else 0,
            ),
            reverse=True,
        )
        return [document for _, document in ranked_documents[:1]]


class ECRIGuidelineConnector(BaseConnector):
    connector_name = "ecri"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._transport = transport

    async def _search_hits(self, task: SpecialistTask, normalized_query: NormalizedQuery) -> list[dict]:
        query = _compile_ecri_query(normalized_query, task)
        params = {
            "q": query,
            "sort": "relevance",
            "s": "0",
            "e": str(max(task.desired_result_count, self.settings.ecri_page_size)),
        }
        async with httpx.AsyncClient(
            base_url=self.settings.ecri_base_url,
            follow_redirects=True,
            timeout=30.0,
            transport=self._transport,
        ) as client:
            response = await client.get("/api/public/briefs", params=params)
            response.raise_for_status()
            payload = response.json()
        ranked_hits: list[tuple[tuple[int, int], dict]] = []
        for hit in payload.get("hits", []):
            rank = _rank_ecri_hit(hit, task)
            if rank[0] <= 0:
                continue
            ranked_hits.append((rank, hit))
        ranked_hits.sort(key=lambda item: item[0], reverse=True)
        return [hit for _, hit in ranked_hits]

    async def _fetch_guideline_text(self, url: str) -> tuple[str, str | None, str | None]:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                transport=self._transport,
                headers={"User-Agent": "Chiron/0.1 guideline-fetch"},
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError:
            return "network_error", None, None

        content_type = (response.headers.get("content-type") or "").lower()
        if response.status_code >= 400:
            return f"http_{response.status_code}", content_type, None

        parsed_url = urlparse(str(response.url))
        path = parsed_url.path.lower()
        if "pdf" in content_type or path.endswith(".pdf"):
            text = _extract_pdf_text(
                response.content,
                max_pages=self.settings.guideline_document_max_pages,
                max_chars=self.settings.guideline_document_max_chars,
            )
            return ("accessible" if text else "pdf_unreadable"), content_type, text

        if "html" in content_type or "text/plain" in content_type or not content_type:
            try:
                body = response.text
            except UnicodeDecodeError:
                body = response.content.decode("utf-8", errors="ignore")
            text = _extract_html_text(body, max_chars=self.settings.guideline_document_max_chars)
            return ("accessible" if text else "html_unreadable"), content_type, text

        return "unsupported_content_type", content_type, None

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        hits = await self._search_hits(task, normalized_query)
        documents: list[SourceDocument] = []
        inaccessible_candidates: list[SourceDocument] = []

        for hit in hits[: max(task.desired_result_count, self.settings.ecri_page_size)]:
            title = hit.get("guidelineTitle") or "Untitled guideline"
            source_text = hit.get("source") or ""
            original_url = hit.get("accessTheGuideline") or f"{self.settings.ecri_base_url}/public"
            trust_scorecard_url = _extract_markdown_link(source_text, "GUIDELINE PROFILE & TRUST SCORECARD")
            pubmed_url = _extract_markdown_link(source_text, "PubMed")
            publication_date = _parse_publication_date(
                hit.get("publicationReaffirmationDate"),
                hit.get("publicationYear"),
            )
            publisher = None
            organizations = hit.get("organizations") or []
            if organizations:
                publisher = organizations[0].get("title")

            access_status, content_type, full_text = await self._fetch_guideline_text(original_url)
            common_metadata = {
                "source_mode": "ecri",
                "ecri_guideline_id": hit.get("uniqueId"),
                "access_status": access_status,
                "original_url": original_url,
                "trust_scorecard_url": trust_scorecard_url,
                "pubmed_url": pubmed_url,
                "meets_revised_inclusion_criteria": hit.get("meetsRevisedInclusionCriteria"),
                "has_quality_rating": hit.get("isGuidelineHaveQuality"),
                "has_recommendation_rating": hit.get("isGuidelineRateQuality"),
                "content_type": content_type,
            }

            if full_text:
                excerpt = _select_relevant_excerpt(full_text, task) or _collapse_whitespace(source_text)[:1800]
                documents.append(
                    SourceDocument(
                        source_id=f"ecri-{hit.get('uniqueId')}",
                        source_type="guideline",
                        title=title,
                        url=original_url,
                        publication_date=publication_date,
                        publisher=publisher,
                        abstract=excerpt,
                        full_text=full_text,
                        metadata=common_metadata,
                    )
                )
            else:
                inaccessible_candidates.append(
                    SourceDocument(
                        source_id=f"ecri-candidate-{hit.get('uniqueId')}",
                        source_type="guideline_candidate",
                        title=title,
                        url=original_url,
                        publication_date=publication_date,
                        publisher=publisher,
                        abstract=(
                            f"ECRI identified this guideline candidate, but the original document was not accessible "
                            f"at retrieval time ({access_status})."
                        ),
                        full_text=None,
                        metadata=common_metadata,
                    )
                )

        ranked_accessible = sorted(
            documents,
            key=lambda document: (
                document.publication_date.toordinal() if document.publication_date else 0,
                1 if document.metadata.get("has_recommendation_rating") else 0,
                1 if document.metadata.get("has_quality_rating") else 0,
            ),
            reverse=True,
        )
        if ranked_accessible:
            return ranked_accessible[: task.desired_result_count]
        return inaccessible_candidates[:1]
