from __future__ import annotations

from app.connectors.guidelines import GuidelineFixtureConnector
from app.core.config import Settings
from app.schemas.common import NormalizedQuery, ScopeDecision, SpecialistTask


async def test_guideline_fixture_connector_returns_curated_match() -> None:
    connector = GuidelineFixtureConnector(settings=Settings(guideline_connector_mode="fixture"))
    normalized_query = NormalizedQuery(
        raw_question="Latest treatment guidance for drug-resistant tuberculosis in pregnancy",
        normalized_question="Current treatment guidance for drug-resistant tuberculosis in pregnancy",
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
    )
    task = SpecialistTask(
        task_id="task-guideline",
        agent_type="guideline",
        objective="Lookup guideline evidence",
        query_text=normalized_query.normalized_question,
        source_query=normalized_query.normalized_question,
        focus_terms=["drug-resistant tuberculosis", "pregnancy"],
    )
    documents = await connector.search(normalized_query, task)
    assert len(documents) == 1
    assert documents[0].source_type == "guideline"
    assert documents[0].metadata["source_mode"] == "fixture"


async def test_guideline_fixture_connector_prefers_general_tb_record_for_non_resistant_query() -> None:
    connector = GuidelineFixtureConnector(settings=Settings(guideline_connector_mode="fixture"))
    normalized_query = NormalizedQuery(
        raw_question="Latest treatment guidance for tuberculosis in pregnancy",
        normalized_question="Current treatment guidance for tuberculosis in pregnancy",
        intent_summary="Test query",
        scope=ScopeDecision(in_scope=True),
    )
    task = SpecialistTask(
        task_id="task-guideline-general",
        agent_type="guideline",
        objective="Lookup guideline evidence",
        query_text=normalized_query.normalized_question,
        source_query=normalized_query.normalized_question,
        focus_terms=["tuberculosis", "pregnancy"],
    )
    documents = await connector.search(normalized_query, task)
    assert len(documents) == 1
    assert documents[0].source_id == "guideline_tb_general_pregnancy_fixture_001"
