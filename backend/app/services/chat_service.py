from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.specialists import RetrievalSpecialist
from app.connectors.clinicaltrials import ClinicalTrialsConnector
from app.connectors.dailymed import DailyMedConnector
from app.connectors.guidelines import GuidelineFixtureConnector
from app.connectors.pubmed import PubMedConnector
from app.core.config import get_settings
from app.connectors.mock import (
    MockDrugSafetyConnector,
    MockGuidelineConnector,
    MockLiteratureConnector,
    MockTrialsConnector,
)
from app.orchestration.graph import build_graph
from app.persistence.models import ChatSession, Run, RunStep
from app.schemas.common import AssistantResponse
from app.schemas.session import MessageCreateRequest
from app.services import session_service


def build_specialists() -> dict[str, RetrievalSpecialist]:
    settings = get_settings()
    literature_connector = (
        PubMedConnector(settings=settings)
        if settings.literature_connector_mode == "pubmed"
        else MockLiteratureConnector()
    )
    trials_connector = (
        ClinicalTrialsConnector(settings=settings)
        if settings.trials_connector_mode == "clinicaltrials"
        else MockTrialsConnector()
    )
    drug_safety_connector = (
        DailyMedConnector(settings=settings)
        if settings.drug_safety_connector_mode == "dailymed"
        else MockDrugSafetyConnector()
    )
    guideline_connector = (
        GuidelineFixtureConnector(settings=settings)
        if settings.guideline_connector_mode == "fixture"
        else MockGuidelineConnector()
    )
    return {
        "guideline": RetrievalSpecialist("guideline", guideline_connector),
        "literature": RetrievalSpecialist("literature", literature_connector),
        "drug_safety": RetrievalSpecialist("drug_safety", drug_safety_connector),
        "trials": RetrievalSpecialist("trials", trials_connector),
    }


graph = build_graph(build_specialists())


async def process_user_message(
    db: AsyncSession, session_id: str, payload: MessageCreateRequest, owner_id: str
) -> tuple[str, AssistantResponse]:
    chat_session = await session_service.get_session(db, session_id, owner_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.role != "user":
        raise HTTPException(status_code=400, detail="Only user messages can be submitted to the chat endpoint")

    user_message = await session_service.create_message(db, session_id, payload, owner_id)
    run = await session_service.create_run(db, session_id, user_message.id)
    state = {
        "session_id": session_id,
        "run_id": run.id,
        "user_message_id": user_message.id,
        "user_question": payload.content,
        "session_context": chat_session.context_json or {},
        "iteration": 0,
        "step_trace": [],
        "completed_tasks": [],
        "sources": [],
        "evidence_items": [],
        "unresolved_gaps": [],
    }
    result = await graph.ainvoke(state)

    final_response = AssistantResponse.model_validate(result["final_response"])
    stored_response = {
        **final_response.model_dump(mode="json"),
        "run_id": run.id,
    }
    assistant_content = (
        final_response.answer
        or final_response.clarification_question
        or final_response.abstention_reason
        or "No response generated."
    )
    await session_service.create_message(
        db,
        session_id,
        MessageCreateRequest(role="assistant", content=assistant_content),
        owner_id,
        metadata_json=stored_response,
    )
    await session_service.update_run(
        db,
        run,
        status="completed",
        iteration_count=int(result.get("iteration", 0)),
        final_status=final_response.status,
        final_response_json=stored_response,
    )
    await session_service.store_run_steps(db, run.id, result.get("step_trace", []))
    return run.id, final_response


async def get_run(db: AsyncSession, run_id: str, owner_id: str) -> Run | None:
    result = await db.execute(
        select(Run).join(ChatSession, ChatSession.id == Run.session_id).where(Run.id == run_id, ChatSession.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def list_run_steps(db: AsyncSession, run_id: str, owner_id: str) -> list[RunStep]:
    result = await db.execute(
        select(RunStep)
        .join(Run, Run.id == RunStep.run_id)
        .join(ChatSession, ChatSession.id == Run.session_id)
        .where(RunStep.run_id == run_id, ChatSession.owner_id == owner_id)
        .order_by(RunStep.step_order.asc())
    )
    return list(result.scalars())
