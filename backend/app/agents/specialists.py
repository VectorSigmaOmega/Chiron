from __future__ import annotations

import re

from app.connectors.base import BaseConnector
from app.schemas.common import EvidenceItem, ParsedQuery, SourceDocument, SpecialistTask


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _modifier_aliases(modifier: str) -> list[str]:
    alias_map = {
        "pregnancy": ["pregnan", "maternal"],
        "hiv": ["hiv", "hiv-positive", "hiv positive"],
        "aids": ["aids"],
        "diabetes": ["diabetes", "diabetic"],
        "renal_impairment": ["renal impairment", "kidney disease", "renal failure", "ckd"],
        "hepatic_impairment": ["hepatic impairment", "liver disease", "liver failure", "cirrhosis"],
        "pediatric": ["pediatric", "paediatric", "child", "children"],
        "geriatric": ["elderly", "older adult", "geriatric"],
        "immunocompromised": ["immunocompromised", "immunosuppressed"],
        "lactation": ["breastfeeding", "lactation"],
        "drug_resistant": ["drug-resistant", "multidrug-resistant", "rifampicin-resistant", "mdr-tb", "rr-tb"],
    }
    return alias_map.get(modifier, [modifier.replace("_", " ")])


def _source_priority(source_type: str) -> int:
    return {"guideline": 4, "review": 3, "label": 3, "study": 2, "registry": 1}.get(source_type, 1)


def _evidence_strength(document: SourceDocument) -> str:
    if document.source_type == "guideline":
        return "high"
    if document.source_type in {"review", "label"}:
        return "moderate"
    return "low"


def _supports_dimensions(parsed_query: ParsedQuery, task: SpecialistTask, document: SourceDocument) -> list[str]:
    dimensions: list[str] = []
    text = " ".join(
        [
            parsed_query.original_question,
            task.goal,
            document.title,
            document.abstract or "",
            " ".join(document.metadata.get("warnings", [])),
        ]
    ).lower()
    if _contains_any(text, ["treatment", "therapy", "regimen", "management", "guideline"]):
        dimensions.append("treatment")
    if _contains_any(text, ["safety", "warning", "adverse", "toxicity", "contraindication", "qt prolongation"]):
        dimensions.append("safety")
    if document.source_type == "registry":
        dimensions.append("trial_status")
    if parsed_query.recency_required and document.publication_date is not None:
        dimensions.append("recency")
    requested_modifiers = set(parsed_query.clinical_modifiers)
    modifier_text = " ".join([document.title, document.abstract or "", document.metadata.get("population", "")]).lower()
    if requested_modifiers and any(
        any(alias in modifier_text for alias in _modifier_aliases(modifier))
        for modifier in requested_modifiers
    ):
        dimensions.append("population")
    return sorted(set(dimensions))


def _claim_type(parsed_query: ParsedQuery, task: SpecialistTask, document: SourceDocument) -> str:
    if document.source_type == "guideline":
        return "recommendation"
    if document.source_type == "label":
        return "safety"
    if document.source_type == "registry":
        return "trial_status"
    text = " ".join([task.goal, parsed_query.original_question, document.title, document.abstract or ""]).lower()
    if _contains_any(text, ["safety", "adverse", "warning", "toxicity", "contraindication"]):
        return "safety"
    if _contains_any(text, ["trial", "phase", "recruiting", "completed"]):
        return "trial_status"
    return "treatment"


def _applicability(parsed_query: ParsedQuery, document: SourceDocument) -> str:
    requested_modifiers = {
        modifier
        for modifier in parsed_query.clinical_modifiers
        if modifier not in {"adult", "outpatient", "inpatient"}
    }
    if not parsed_query.population and not parsed_query.pregnancy_status and not requested_modifiers:
        return "general"
    text = " ".join(
        [document.title, document.abstract or "", document.metadata.get("population", ""), document.metadata.get("condition", "")]
    ).lower()
    matched_modifiers = {
        modifier
        for modifier in requested_modifiers
        if any(alias in text for alias in _modifier_aliases(modifier))
    }
    if requested_modifiers:
        return "direct" if matched_modifiers == requested_modifiers else "indirect"
    if parsed_query.population and parsed_query.population.lower() in text:
        return "direct"
    return "general"


def _uncertainty_notes(document: SourceDocument) -> list[str]:
    notes: list[str] = []
    abstract = (document.abstract or "").lower()
    if document.source_type == "registry":
        notes.append("Registry records can indicate emerging evidence but do not establish comparative clinical effectiveness.")
    if document.source_type == "study":
        notes.append("Single-study evidence should be interpreted in context of broader reviews or guidelines.")
    if _contains_any(abstract, ["limited", "sparse", "insufficient", "uncertain", "observational"]):
        notes.append("The source text explicitly signals limited or uncertain evidence.")
    return sorted(set(notes))


def _limitations(document: SourceDocument) -> list[str]:
    limitations: list[str] = []
    abstract = (document.abstract or "").lower()
    if document.source_type == "registry":
        limitations.append("Trial registry entries do not provide full peer-reviewed outcome evidence.")
    if document.source_type == "label":
        limitations.append("Drug labels are authoritative for warnings but do not answer comparative treatment efficacy.")
    if document.source_type == "study" and not document.abstract:
        limitations.append("No abstract was available from the current PubMed retrieval path.")
    if _contains_any(abstract, ["observational", "case series", "retrospective"]):
        limitations.append("The evidence appears observational and may be affected by confounding.")
    if _contains_any(abstract, ["limited", "insufficient", "sparse"]):
        limitations.append("The source text indicates limited available evidence.")
    return sorted(set(limitations))


def _key_claim(document: SourceDocument) -> str:
    text = (document.abstract or document.title).strip()
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
    parsed_query: ParsedQuery,
    task: SpecialistTask,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for index, document in enumerate(documents, start=1):
        safety_notes = list(document.metadata.get("warnings", []))
        candidate_drugs = list(document.metadata.get("candidate_drugs", []))
        if not safety_notes and document.abstract and _contains_any(
            document.abstract,
            ["qt prolongation", "hepatotoxicity", "boxed warning", "contraindication", "neuropathy"],
        ):
            extracted = []
            for signal in [
                "qt prolongation",
                "hepatotoxicity",
                "boxed warning",
                "contraindication",
                "neuropathy",
            ]:
                if signal in document.abstract.lower():
                    extracted.append(signal)
            safety_notes = extracted
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
                claim_type=_claim_type(parsed_query, task, document),
                applicability=_applicability(parsed_query, document),
                supports_question_dimensions=_supports_dimensions(parsed_query, task, document),
                safety_notes=safety_notes,
                limitations=_limitations(document),
                uncertainty_notes=_uncertainty_notes(document),
                evidence_strength=_evidence_strength(document),
                source_priority=_source_priority(document.source_type),
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
        evidence = build_evidence_items(documents, parsed_query=parsed_query, task=task)
        return documents, evidence
