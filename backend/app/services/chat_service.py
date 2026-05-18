from __future__ import annotations

import asyncio

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
from app.core.db import SessionLocal
from app.orchestration.graph import build_graph
from app.persistence.models import ChatSession, Run, RunStep
from app.schemas.common import AssistantResponse, EntityRef, EvidenceItem, ParsedQuery
from app.schemas.session import MessageCreateRequest
from app.services import session_service
from app.services.progress_service import get_progress_service


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
progress_service = get_progress_service()


def _merge_unique_str(left: list[str], right: list[str]) -> list[str]:
    return list(dict.fromkeys([*left, *right]))


def _build_session_context(previous_context: dict, result: dict, final_response: AssistantResponse) -> dict:
    parsed_query = ParsedQuery.model_validate(result.get("parsed_query", {}))
    evidence_items = [EvidenceItem.model_validate(item) for item in result.get("evidence_items", [])]
    previous_entities = [EntityRef.model_validate(item) for item in previous_context.get("active_entities", [])]

    current_entities = parsed_query.entities or previous_entities
    medications = _merge_unique_str(
        list(previous_context.get("medications", [])),
        _merge_unique_str(
            parsed_query.medications,
            [entity.name for entity in parsed_query.entities if entity.kind.lower() == "drug"]
            + [drug for item in evidence_items for drug in item.extracted_entities],
        ),
    )

    return {
        "active_entities": [entity.model_dump(mode="json") for entity in current_entities],
        "clinical_modifiers": _merge_unique_str(
            list(previous_context.get("clinical_modifiers", [])),
            parsed_query.clinical_modifiers,
        ),
        "comorbidities": _merge_unique_str(
            list(previous_context.get("comorbidities", [])),
            parsed_query.comorbidities,
        ),
        "medications": medications,
        "population": parsed_query.population or previous_context.get("population"),
        "setting": parsed_query.setting or previous_context.get("setting"),
        "last_question": parsed_query.original_question,
        "last_answer_status": final_response.status,
        "last_question_roles": list(
            dict.fromkeys(
                [
                    (item.question_role or item.claim_type or "background")
                    for item in evidence_items[:4]
                ]
            )
        ),
    }


def _build_run_state(
    *,
    session_id: str,
    run_id: str,
    user_message_id: str,
    user_question: str,
    session_context: dict,
) -> dict:
    return {
        "session_id": session_id,
        "run_id": run_id,
        "user_message_id": user_message_id,
        "user_question": user_question,
        "session_context": session_context,
        "iteration": 0,
        "step_trace": [],
        "completed_tasks": [],
        "sources": [],
        "evidence_items": [],
        "unresolved_gaps": [],
        "emit_progress": lambda event: progress_service.publish(run_id, event),
    }


async def _execute_run_graph(
    db: AsyncSession,
    *,
    chat_session: ChatSession,
    run: Run,
    user_message_id: str,
    user_question: str,
    owner_id: str,
) -> AssistantResponse:
    state = _build_run_state(
        session_id=chat_session.id,
        run_id=run.id,
        user_message_id=user_message_id,
        user_question=user_question,
        session_context=chat_session.context_json or {},
    )
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
        chat_session.id,
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
    updated_context = _build_session_context(chat_session.context_json or {}, result, final_response)
    await session_service.update_session_context(db, chat_session.id, owner_id, updated_context)
    await session_service.store_run_steps(db, run.id, result.get("step_trace", []))
    progress_service.publish(
        run.id,
        {
            "type": "final",
            "message": "Response ready.",
            "response": stored_response,
        },
    )
    progress_service.finish(run.id)
    return final_response


async def _run_in_background(
    *,
    session_id: str,
    run_id: str,
    user_message_id: str,
    user_question: str,
    owner_id: str,
) -> None:
    async with SessionLocal() as db:
        try:
            chat_session = await session_service.get_session(db, session_id, owner_id)
            if chat_session is None:
                progress_service.publish(
                    run_id,
                    {"type": "error", "message": "Session not found for background run."},
                )
                progress_service.finish(run_id)
                return
            run = await get_run(db, run_id, owner_id)
            if run is None:
                progress_service.publish(
                    run_id,
                    {"type": "error", "message": "Run not found for background execution."},
                )
                progress_service.finish(run_id)
                return
            await _execute_run_graph(
                db,
                chat_session=chat_session,
                run=run,
                user_message_id=user_message_id,
                user_question=user_question,
                owner_id=owner_id,
            )
        except Exception as exc:
            run = await get_run(db, run_id, owner_id)
            if run is not None:
                run.status = "failed"
                run.final_status = "abstained"
                run.final_response_json = {"error": str(exc)}
                await db.commit()
            progress_service.publish(
                run_id,
                {"type": "error", "message": f"Run failed: {exc}"},
            )
            progress_service.finish(run_id)


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
    progress_service.start_run(run.id)
    progress_service.publish(
        run.id,
        {"type": "status", "message": "Starting consultation."},
    )
    final_response = await _execute_run_graph(
        db,
        chat_session=chat_session,
        run=run,
        user_message_id=user_message.id,
        user_question=payload.content,
        owner_id=owner_id,
    )
    return run.id, final_response


async def start_user_message_run(
    db: AsyncSession, session_id: str, payload: MessageCreateRequest, owner_id: str
) -> str:
    chat_session = await session_service.get_session(db, session_id, owner_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.role != "user":
        raise HTTPException(status_code=400, detail="Only user messages can be submitted to the chat endpoint")

    user_message = await session_service.create_message(db, session_id, payload, owner_id)
    run = await session_service.create_run(db, session_id, user_message.id)
    progress_service.start_run(run.id)
    progress_service.publish(
        run.id,
        {"type": "status", "message": "Starting consultation."},
    )
    asyncio.create_task(
        _run_in_background(
            session_id=session_id,
            run_id=run.id,
            user_message_id=user_message.id,
            user_question=payload.content,
            owner_id=owner_id,
        )
    )
    return run.id


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
