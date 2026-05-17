from __future__ import annotations

from datetime import date
from xml.etree import ElementTree

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import ParsedQuery, SourceDocument, SpecialistTask


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


def _extract_drug_name(parsed_query: ParsedQuery, task: SpecialistTask) -> str | None:
    for entity in task.focus_entities:
        cleaned = entity.strip()
        if cleaned and cleaned.lower() not in {"drug-resistant tuberculosis", "tuberculosis"}:
            return cleaned
    for entity in parsed_query.entities:
        if entity.kind == "drug":
            return entity.name
    return None


def _xml_text(root: ElementTree.Element) -> str:
    return " ".join(part.strip() for part in root.itertext() if part and part.strip())


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

    async def search(self, parsed_query: ParsedQuery, task: SpecialistTask) -> list[SourceDocument]:
        drug_name = _extract_drug_name(parsed_query, task)
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
                flattened = _xml_text(root)
                safety_notes = []
                for signal in ["qt prolongation", "hepatotoxicity", "boxed warning", "contraindications"]:
                    if signal in flattened.lower():
                        safety_notes.append(signal)
                documents.append(
                    SourceDocument(
                        source_id=setid,
                        source_type="label",
                        title=record.get("title") or f"DailyMed label for {drug_name}",
                        url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
                        publication_date=_parse_dailymed_date(record.get("published_date")),
                        publisher="DailyMed",
                        abstract=" ".join(safety_notes) if safety_notes else None,
                        full_text=None,
                        metadata={
                            "drug": drug_name,
                            "spl_version": record.get("spl_version"),
                            "warnings": safety_notes,
                        },
                    )
                )
            return documents
