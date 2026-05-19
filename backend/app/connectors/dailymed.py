from __future__ import annotations

from datetime import date
from xml.etree import ElementTree
import re

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask


def _parse_dailymed_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.replace(",", "")
    parts = cleaned.split()
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
    if len(parts) != 3:
        return None
    month = month_map.get(parts[0][:3])
    if month is None:
        return None
    try:
        day = int(parts[1])
        year = int(parts[2])
    except ValueError:
        return None
    return date(year, month, day)


def _extract_drug_name(normalized_query: NormalizedQuery, task: SpecialistTask) -> str | None:
    for term in task.intervention_terms:
        cleaned = term.strip()
        if cleaned:
            return cleaned
    for term in task.focus_terms:
        cleaned = term.strip()
        if cleaned:
            return cleaned
    for entity in normalized_query.entities:
        if entity.category.lower() in {"drug", "medication", "therapy", "intervention"}:
            return entity.normalized_text or entity.text
    if task.source_query.strip():
        return task.source_query.strip()
    return None


def _xml_text(root: ElementTree.Element) -> str:
    return " ".join(part.strip() for part in root.itertext() if part and part.strip())


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section_text(root: ElementTree.Element, keywords: list[str]) -> str | None:
    keyword_set = {keyword.lower() for keyword in keywords}
    for section in root.findall(".//{*}section"):
        title = section.find(".//{*}title")
        title_text = _normalize_whitespace("".join(title.itertext())) if title is not None else ""
        if title_text.lower() in keyword_set:
            return _normalize_whitespace(_xml_text(section))
    return None


def _build_label_summary(
    *,
    title: str,
    boxed_warning_text: str | None,
    warnings_text: str | None,
    contraindications_text: str | None,
) -> str:
    fragments = [title]
    if boxed_warning_text:
        fragments.append(boxed_warning_text[:260] + ("..." if len(boxed_warning_text) > 260 else ""))
    elif warnings_text:
        fragments.append(warnings_text[:260] + ("..." if len(warnings_text) > 260 else ""))
    if contraindications_text:
        cleaned = contraindications_text[:180] + ("..." if len(contraindications_text) > 180 else "")
        fragments.append(f"Contraindications: {cleaned}")
    return " ".join(fragment for fragment in fragments if fragment).strip()


class DailyMedConnector(BaseConnector):
    connector_name = "dailymed"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    async def _lookup_setids(self, client: httpx.AsyncClient, drug_name: str) -> list[dict]:
        response = await client.get(
            "/spls.json",
            params={"drug_name": drug_name, "pagesize": str(self.settings.dailymed_page_size)},
        )
        response.raise_for_status()
        return list(response.json().get("data", []))

    async def _fetch_label_xml(self, client: httpx.AsyncClient, setid: str) -> str:
        response = await client.get(f"/spls/{setid}.xml")
        response.raise_for_status()
        return response.text

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        drug_name = _extract_drug_name(normalized_query, task)
        if not drug_name:
            return []
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(
            base_url=self.settings.dailymed_base_url,
            timeout=timeout,
            transport=self.transport,
        ) as client:
            records = await self._lookup_setids(client, drug_name)
            documents: list[SourceDocument] = []
            for record in records[: self.settings.dailymed_page_size]:
                setid = record.get("setid")
                if not setid:
                    continue
                xml_text = await self._fetch_label_xml(client, setid)
                root = ElementTree.fromstring(xml_text)
                boxed_warning_text = _section_text(root, ["boxed warning"])
                warnings_text = _section_text(root, ["warnings and precautions", "warnings"])
                contraindications_text = _section_text(root, ["contraindications"])
                title = record.get("title") or f"DailyMed label for {drug_name}"
                documents.append(
                    SourceDocument(
                        source_id=setid,
                        source_type="label",
                        title=title,
                        url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
                        publication_date=_parse_dailymed_date(record.get("published_date")),
                        publisher="DailyMed",
                        abstract=_build_label_summary(
                            title=title,
                            boxed_warning_text=boxed_warning_text,
                            warnings_text=warnings_text,
                            contraindications_text=contraindications_text,
                        ),
                        full_text=None,
                        metadata={
                            "drug": drug_name,
                            "spl_version": record.get("spl_version"),
                            "boxed_warning_excerpt": boxed_warning_text,
                            "warnings_excerpt": warnings_text,
                            "contraindications_excerpt": contraindications_text,
                        },
                    )
                )
            return documents
