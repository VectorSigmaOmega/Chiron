from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import ParsedQuery, SourceDocument, SpecialistTask


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _summarize_interventions(interventions_module: dict[str, Any]) -> list[str]:
    interventions = []
    for intervention in interventions_module.get("interventions", []):
        name = intervention.get("name")
        if name:
            interventions.append(name)
    return interventions


class ClinicalTrialsConnector(BaseConnector):
    connector_name = "clinicaltrials"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    @staticmethod
    def _condition_term(parsed_query: ParsedQuery, task: SpecialistTask) -> str | None:
        for entity in task.focus_entities:
            lowered = entity.lower()
            if any(token in lowered for token in ["tuberculosis", "pneumonia", "sepsis", "cancer"]):
                return entity
        for entity in parsed_query.entities:
            if entity.kind == "condition":
                return entity.name
        return None

    async def search(self, parsed_query: ParsedQuery, task: SpecialistTask) -> list[SourceDocument]:
        timeout = httpx.Timeout(20.0, connect=10.0)
        params = {"pageSize": str(self.settings.clinicaltrials_page_size)}
        condition_term = self._condition_term(parsed_query, task)
        if condition_term:
            params["query.cond"] = condition_term
        else:
            params["query.term"] = task.subquery or parsed_query.rewritten_question
        async with httpx.AsyncClient(
            base_url=self.settings.clinicaltrials_base_url,
            timeout=timeout,
            transport=self.transport,
        ) as client:
            response = await client.get("/studies", params=params)
            response.raise_for_status()
            payload = response.json()

        documents: list[SourceDocument] = []
        for study in payload.get("studies", []):
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            description = protocol.get("descriptionModule", {})
            arms = protocol.get("armsInterventionsModule", {})
            conditions = protocol.get("conditionsModule", {})
            nct_id = identification.get("nctId")
            if not nct_id:
                continue
            interventions = _summarize_interventions(arms)
            documents.append(
                SourceDocument(
                    source_id=nct_id,
                    source_type="registry",
                    title=identification.get("briefTitle")
                    or identification.get("officialTitle")
                    or f"Clinical trial {nct_id}",
                    url=f"https://clinicaltrials.gov/study/{nct_id}",
                    publication_date=_parse_iso_date(
                        status.get("lastUpdatePostDateStruct", {}).get("date")
                        or status.get("studyFirstPostDateStruct", {}).get("date")
                    ),
                    publisher="ClinicalTrials.gov",
                    abstract=description.get("briefSummary"),
                    full_text=None,
                    metadata={
                        "overall_status": status.get("overallStatus"),
                        "phase": protocol.get("designModule", {}).get("phases", []),
                        "conditions": conditions.get("conditions", []),
                        "interventions": interventions,
                    },
                )
            )
        return documents
