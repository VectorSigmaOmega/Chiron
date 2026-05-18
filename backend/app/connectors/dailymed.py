from __future__ import annotations

from datetime import date
from xml.etree import ElementTree
import re

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
    for medication in parsed_query.medications:
        cleaned = medication.strip()
        if cleaned:
            return cleaned
    return None


def _xml_text(root: ElementTree.Element) -> str:
    return " ".join(part.strip() for part in root.itertext() if part and part.strip())


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_warning_signals(text: str) -> list[str]:
    haystack = text.lower()
    signal_map = [
        ("qt prolongation", ["qt prolongation", "prolongation of the qt"]),
        ("hepatotoxicity", ["hepatotoxicity", "hepatic adverse"]),
        ("boxed warning", ["boxed warning"]),
        ("contraindications", ["contraindication", "contraindications"]),
        ("myelosuppression", ["myelosuppression"]),
        ("peripheral neuropathy", ["peripheral neuropathy", "neuropathy"]),
        ("embryo-fetal toxicity", ["embryo-fetal toxicity", "fetal toxicity", "pregnancy"]),
        ("drug interactions", ["drug interactions", "interaction"]),
    ]
    extracted: list[str] = []
    for label, needles in signal_map:
        if any(needle in haystack for needle in needles):
            extracted.append(label)
    return extracted


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
    warning_signals: list[str],
    boxed_warning_text: str | None,
    warnings_text: str | None,
    contraindications_text: str | None,
) -> str:
    fragments = [title]
    if warning_signals:
        fragments.append(f"Key label signals: {', '.join(warning_signals)}.")
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
                safety_notes = _extract_warning_signals(flattened)
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
                            warning_signals=safety_notes,
                            boxed_warning_text=boxed_warning_text,
                            warnings_text=warnings_text,
                            contraindications_text=contraindications_text,
                        ),
                        full_text=None,
                        metadata={
                            "drug": drug_name,
                            "spl_version": record.get("spl_version"),
                            "warnings": safety_notes,
                            "boxed_warning_excerpt": boxed_warning_text,
                            "warnings_excerpt": warnings_text,
                            "contraindications_excerpt": contraindications_text,
                        },
                    )
                )
            return documents
