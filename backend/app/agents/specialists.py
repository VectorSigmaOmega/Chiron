from __future__ import annotations

import re

from app.connectors.base import BaseConnector
from app.schemas.common import EvidenceItem, NormalizedQuery, SourceDocument, SpecialistTask


def _source_priority(source_type: str) -> int:
    return {"guideline": 4, "review": 3, "label": 3, "study": 2, "registry": 1, "guideline_candidate": 1}.get(source_type, 1)


def _evidence_strength(document: SourceDocument) -> str:
    if document.source_type == "guideline":
        return "high"
    if document.source_type == "guideline_candidate":
        return "low"
    if document.source_type in {"review", "label"}:
        return "moderate"
    return "low"


def _uncertainty_notes(document: SourceDocument) -> list[str]:
    notes: list[str] = []
    abstract = (document.abstract or "").lower()
    access_status = document.metadata.get("access_status")
    if document.source_type == "guideline_candidate":
        notes.append("This item captures guideline discovery metadata rather than accessible recommendation text.")
    if access_status and access_status != "accessible":
        notes.append(f"The original source document was not fully accessible at retrieval time ({access_status}).")
    if document.source_type == "registry":
        notes.append("Registry records can indicate emerging evidence but do not establish comparative clinical effectiveness.")
    if document.source_type == "study":
        notes.append("Single-study evidence should be interpreted in context of broader reviews or guidelines.")
    if any(token in abstract for token in ["limited", "sparse", "insufficient", "uncertain", "observational"]):
        notes.append("The source text explicitly signals limited or uncertain evidence.")
    return sorted(set(notes))


def _limitations(document: SourceDocument) -> list[str]:
    limitations: list[str] = []
    abstract = (document.abstract or "").lower()
    access_status = document.metadata.get("access_status")
    if document.source_type == "guideline_candidate":
        limitations.append("The original guideline document could not be accessed, so only discovery metadata is available.")
    if access_status and access_status != "accessible":
        limitations.append(f"The source document was not directly accessible during retrieval ({access_status}).")
    if document.source_type == "registry":
        limitations.append("Trial registry entries do not provide full peer-reviewed outcome evidence.")
    if document.source_type == "label":
        limitations.append("Drug labels are authoritative for warnings but do not answer comparative treatment efficacy.")
    if document.source_type == "study" and not document.abstract:
        limitations.append("No abstract was available from the current PubMed retrieval path.")
    if any(token in abstract for token in ["observational", "case series", "retrospective"]):
        limitations.append("The evidence appears observational and may be affected by confounding.")
    if any(token in abstract for token in ["limited", "insufficient", "sparse"]):
        limitations.append("The source text indicates limited available evidence.")
    return sorted(set(limitations))


def _key_claim(document: SourceDocument) -> str:
    text = (document.abstract or document.full_text or document.title).strip()
    if not text:
        return document.title
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text) if segment.strip()]
    if not sentences:
        return text
    first_sentence = sentences[0]
    return first_sentence if len(first_sentence) <= 320 else first_sentence[:317] + "..."


def build_evidence_items(
    documents: list[SourceDocument],
    *,
    normalized_query: NormalizedQuery,
    task: SpecialistTask,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for index, document in enumerate(documents, start=1):
        candidate_drugs = list(document.metadata.get("candidate_drugs", []))
        evidence.append(
            EvidenceItem(
                evidence_id=f"{document.source_id}-e{index}",
                source_id=document.source_id,
                source_type=document.source_type,
                title=document.title,
                url=document.url,
                publication_date=document.publication_date,
                publisher=document.publisher,
                population=document.metadata.get("population"),
                intervention=", ".join(candidate_drugs) if candidate_drugs else document.metadata.get("drug"),
                outcome=document.metadata.get("status") or document.metadata.get("overall_status"),
                key_claim=_key_claim(document),
                claim_type=document.source_type,
                applicability=document.metadata.get("population") or None,
                supports_question_dimensions=[],
                safety_notes=[],
                limitations=_limitations(document),
                uncertainty_notes=_uncertainty_notes(document),
                evidence_strength=_evidence_strength(document),
                source_priority=_source_priority(document.source_type),
                extracted_entities=candidate_drugs
                or ([document.metadata["drug"]] if "drug" in document.metadata else task.focus_terms[:3]),
            )
        )
    return evidence


class RetrievalSpecialist:
    def __init__(self, agent_type: str, connector: BaseConnector) -> None:
        self.agent_type = agent_type
        self.connector = connector

    async def run(
        self, normalized_query: NormalizedQuery, task: SpecialistTask
    ) -> tuple[list[SourceDocument], list[EvidenceItem]]:
        documents = await self.connector.search(normalized_query, task)
        evidence = build_evidence_items(documents, normalized_query=normalized_query, task=task)
        return documents, evidence
