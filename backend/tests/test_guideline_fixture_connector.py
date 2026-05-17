from __future__ import annotations

from app.connectors.guidelines import GuidelineFixtureConnector
from app.core.config import Settings
from app.schemas.common import ParsedQuery, SpecialistTask


async def test_guideline_fixture_connector_returns_curated_match() -> None:
    connector = GuidelineFixtureConnector(settings=Settings(guideline_connector_mode="fixture"))
    parsed_query = ParsedQuery(
        original_question="Latest treatment guidance for drug-resistant tuberculosis in pregnancy",
        rewritten_question="Latest treatment guidance for drug-resistant tuberculosis in pregnancy",
    )
    task = SpecialistTask(
        task_id="task-guideline",
        agent_type="guideline",
        goal="Lookup guideline evidence",
        subquery=parsed_query.rewritten_question,
        depends_on=[],
        focus_entities=["drug-resistant tuberculosis"],
    )
    documents = await connector.search(parsed_query, task)
    assert len(documents) == 1
    assert documents[0].source_type == "guideline"
    assert documents[0].metadata["source_mode"] == "fixture"
