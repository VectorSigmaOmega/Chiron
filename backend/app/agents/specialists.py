from __future__ import annotations

from app.connectors.base import BaseConnector
from app.schemas.common import EvidenceItem, ParsedQuery, SourceDocument, SpecialistTask


def build_evidence_items(documents: list[SourceDocument]) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for index, document in enumerate(documents, start=1):
        safety_notes = list(document.metadata.get("warnings", []))
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
                outcome=document.metadata.get("status"),
                key_claim=document.abstract or document.title,
                safety_notes=safety_notes,
                limitations=[
                    "Mock evidence used for scaffold mode; replace with live extraction as connectors mature."
                ],
                evidence_strength="moderate" if document.source_type in {"guideline", "review"} else "low",
                extracted_entities=candidate_drugs or ([document.metadata["drug"]] if "drug" in document.metadata else []),
            )
        )
    return evidence


class RetrievalSpecialist:
    def __init__(self, agent_type: str, connector: BaseConnector) -> None:
        self.agent_type = agent_type
        self.connector = connector

    async def run(
        self, parsed_query: ParsedQuery, task: SpecialistTask
    ) -> tuple[list[SourceDocument], list[EvidenceItem]]:
        documents = await self.connector.search(parsed_query, task)
        evidence = build_evidence_items(documents)
        return documents, evidence
