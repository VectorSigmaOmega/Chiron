from __future__ import annotations

from datetime import date

from app.connectors.base import BaseConnector
from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


class MockGuidelineConnector(BaseConnector):
    connector_name = "mock_guideline"

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        question = normalized_query.normalized_question.lower()
        if _contains_any(question, ["drug-resistant", "mdr-tb", "rr-tb"]):
            return [
                SourceDocument(
                    source_id="guide_tb_pregnancy_001",
                    source_type="guideline",
                    title="Mock TB guideline for pregnancy-aware management",
                    url="https://example.org/guidelines/tb-pregnancy",
                    publication_date=date(2025, 11, 12),
                    publisher="Curated Demo Guideline",
                    abstract="Pregnancy-specific management of drug-resistant TB should involve specialist consultation and individualized risk-benefit review.",
                    metadata={"condition": "drug-resistant tuberculosis", "population": "pregnancy"},
                )
            ]
        if "tuberculosis" in question or "tb" in question:
            abstract = "Standard evidence-based regimens remain the default approach for active tuberculosis in pregnancy when drug susceptibility is expected."
            if "hiv" in question:
                abstract += " In pregnant patients with HIV, co-management and drug interaction review are particularly important."
            return [
                SourceDocument(
                    source_id="guide_tb_general_001",
                    source_type="guideline",
                    title="Mock TB guideline for treatment in pregnancy",
                    url="https://example.org/guidelines/tb-pregnancy-general",
                    publication_date=date(2025, 7, 10),
                    publisher="Curated Demo Guideline",
                    abstract=abstract,
                    metadata={"condition": "tuberculosis", "population": "pregnancy"},
                )
            ]
        if _contains_any(question, ["pneumonia", "sepsis"]):
            return [
                SourceDocument(
                    source_id="guide_general_001",
                    source_type="guideline",
                    title="Mock respiratory infection guidance",
                    url="https://example.org/guidelines/respiratory",
                    publication_date=date(2024, 6, 10),
                    publisher="Curated Demo Guideline",
                    abstract="Management varies by patient age, severity, and care setting.",
                    metadata={"condition": "respiratory infection"},
                )
            ]
        return []


class MockLiteratureConnector(BaseConnector):
    connector_name = "mock_literature"

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        question = normalized_query.normalized_question.lower()
        if _contains_any(question, ["drug-resistant", "mdr-tb", "rr-tb"]):
            return [
                SourceDocument(
                    source_id="pubmed_tb_2026_001",
                    source_type="study",
                    title="Recent observational evidence on drug-resistant TB treatment in pregnancy",
                    url="https://pubmed.ncbi.nlm.nih.gov/mock-tb-pregnancy",
                    publication_date=date(2026, 2, 21),
                    publisher="PubMed",
                    abstract="Bedaquiline-containing regimens remain promising, but pregnancy-specific safety data are limited and specialist oversight is recommended.",
                    metadata={
                        "condition": "drug-resistant tuberculosis",
                        "candidate_drugs": ["bedaquiline", "linezolid"],
                        "mentions_safety_gap": True,
                    },
                )
            ]
        if "tuberculosis" in question or "tb" in question:
            abstract = "Standard evidence-based regimens remain recommended for active tuberculosis in pregnancy, although pregnancy-specific comparative evidence remains limited."
            if "hiv" in question:
                abstract += " Women living with HIV require additional drug interaction review and close monitoring."
            return [
                SourceDocument(
                    source_id="pubmed_tb_general_001",
                    source_type="review",
                    title="Mock review of tuberculosis treatment in pregnancy",
                    url="https://pubmed.ncbi.nlm.nih.gov/mock-tb-general-pregnancy",
                    publication_date=date(2025, 5, 15),
                    publisher="PubMed",
                    abstract=abstract,
                    metadata={"condition": "tuberculosis", "population": "pregnancy"},
                )
            ]
        if "side effect" in question or "adverse" in question:
            return [
                SourceDocument(
                    source_id="pubmed_safety_001",
                    source_type="review",
                    title="Mock review of safety signal interpretation in drug evidence",
                    url="https://pubmed.ncbi.nlm.nih.gov/mock-drug-safety",
                    publication_date=date(2024, 9, 1),
                    publisher="PubMed",
                    abstract="Safety evidence often requires regulatory and label cross-checking rather than literature alone.",
                    metadata={},
                )
            ]
        return []


class MockDrugSafetyConnector(BaseConnector):
    connector_name = "mock_drug_safety"

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        lowered_entities = {entity.normalized_text.lower() for entity in normalized_query.entities}
        focus = " ".join(task.focus_terms).lower()
        if (
            "bedaquiline" in focus
            or "bedaquiline" in lowered_entities
            or "tb" in normalized_query.normalized_question.lower()
        ):
            return [
                SourceDocument(
                    source_id="dailymed_bedaquiline_mock",
                    source_type="label",
                    title="Mock bedaquiline label summary",
                    url="https://dailymed.nlm.nih.gov/mock/bedaquiline",
                    publication_date=date(2025, 4, 2),
                    publisher="DailyMed",
                    abstract="QT prolongation, hepatotoxicity, and drug interaction review are important safety considerations.",
                    metadata={
                        "drug": "bedaquiline",
                        "warnings": ["QT prolongation", "hepatotoxicity"],
                    },
                )
            ]
        return []


class MockTrialsConnector(BaseConnector):
    connector_name = "mock_trials"

    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        question = normalized_query.normalized_question.lower()
        if "tuberculosis" in question or "tb" in question:
            return [
                SourceDocument(
                    source_id="trial_tb_pregnancy_mock",
                    source_type="registry",
                    title="Mock registry record for treatment-shortening drug-resistant TB regimen",
                    url="https://clinicaltrials.gov/study/mock-tb-pregnancy",
                    publication_date=date(2025, 8, 30),
                    publisher="ClinicalTrials.gov",
                    abstract="Registry listing suggests ongoing evaluation of bedaquiline-containing regimens; pregnancy-specific inclusion remains limited.",
                    metadata={"status": "recruiting", "phase": "Phase 3"},
                )
            ]
        return []
