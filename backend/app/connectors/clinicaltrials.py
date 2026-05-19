from __future__ import annotations

from datetime import date
from typing import Any
import re

import httpx

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask


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


def _normalize_status(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("_", " ").replace("-", " ").title()


def _normalize_phase(phases: list[str]) -> list[str]:
    normalized = []
    for phase in phases:
        cleaned = phase.replace("_", " ").title()
        cleaned = re.sub(r"Phase(?=\d)", "Phase ", cleaned)
        normalized.append(cleaned)
    return normalized


def _extract_eligibility_snapshot(eligibility_module: dict[str, Any]) -> dict[str, Any]:
    criteria = eligibility_module.get("eligibilityCriteria")
    if isinstance(criteria, str):
        criteria = re.sub(r"\s+", " ", criteria).strip()
    else:
        criteria = None
    if criteria and len(criteria) > 280:
        criteria = criteria[:277] + "..."
    return {
        "sex": eligibility_module.get("sex"),
        "healthy_volunteers": eligibility_module.get("healthyVolunteers"),
        "ages": eligibility_module.get("stdAges", []),
        "criteria_excerpt": criteria,
    }


def _build_trial_summary(
    *,
    title: str,
    overall_status: str | None,
    phase_labels: list[str],
    conditions: list[str],
    interventions: list[str],
    brief_summary: str | None,
    eligibility_snapshot: dict[str, Any],
) -> str:
    fragments = [title]
    if overall_status:
        fragments.append(f"Status: {overall_status}.")
    if phase_labels:
        fragments.append(f"Phase: {', '.join(phase_labels)}.")
    if conditions:
        fragments.append(f"Conditions: {', '.join(conditions[:3])}.")
    if interventions:
        fragments.append(f"Interventions: {', '.join(interventions[:3])}.")
    if brief_summary:
        fragments.append(brief_summary.strip())
    criteria_excerpt = eligibility_snapshot.get("criteria_excerpt")
    if criteria_excerpt:
        fragments.append(f"Eligibility excerpt: {criteria_excerpt}")
    return " ".join(fragment.strip() for fragment in fragments if fragment).strip()


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

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        timeout = httpx.Timeout(20.0, connect=10.0)
        params = {
            "pageSize": str(min(task.desired_result_count, self.settings.clinicaltrials_page_size)),
            "query.term": task.source_query or task.query_text or normalized_query.normalized_question,
        }
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
            eligibility = protocol.get("eligibilityModule", {})
            nct_id = identification.get("nctId")
            if not nct_id:
                continue
            interventions = _summarize_interventions(arms)
            condition_list = list(conditions.get("conditions", []))
            overall_status = _normalize_status(status.get("overallStatus"))
            phase_labels = _normalize_phase(protocol.get("designModule", {}).get("phases", []))
            brief_summary = description.get("briefSummary")
            eligibility_snapshot = _extract_eligibility_snapshot(eligibility)
            title = (
                identification.get("briefTitle")
                or identification.get("officialTitle")
                or f"Clinical trial {nct_id}"
            )
            documents.append(
                SourceDocument(
                    source_id=nct_id,
                    source_type="registry",
                    title=title,
                    url=f"https://clinicaltrials.gov/study/{nct_id}",
                    publication_date=_parse_iso_date(
                        status.get("lastUpdatePostDateStruct", {}).get("date")
                        or status.get("studyFirstPostDateStruct", {}).get("date")
                    ),
                    publisher="ClinicalTrials.gov",
                    abstract=_build_trial_summary(
                        title=title,
                        overall_status=overall_status,
                        phase_labels=phase_labels,
                        conditions=condition_list,
                        interventions=interventions,
                        brief_summary=brief_summary,
                        eligibility_snapshot=eligibility_snapshot,
                    ),
                    full_text=None,
                    metadata={
                        "overall_status": overall_status,
                        "phase": phase_labels,
                        "conditions": condition_list,
                        "interventions": interventions,
                        "candidate_drugs": interventions,
                        "population": eligibility_snapshot.get("criteria_excerpt"),
                        "eligibility": eligibility_snapshot,
                    },
                )
            )
        return documents
