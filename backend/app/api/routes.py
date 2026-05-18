from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_anonymous_client_id
from app.core.config import get_settings
from app.core.db import get_db_session
from app.schemas.session import (
    MessageCreateRequest,
    MessageOut,
    MessageRunResponse,
    RunOut,
    RunStepOut,
    SessionCreateRequest,
    SessionOut,
)
from app.services import chat_service, session_service

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "llm_mode": settings.llm_mode,
    }


@router.post("/sessions", response_model=SessionOut)
async def create_session(
    payload: SessionCreateRequest,
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> SessionOut:
    session = await session_service.create_session(db, client_id, payload.title)
    return SessionOut.model_validate(session, from_attributes=True)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[SessionOut]:
    sessions = await session_service.list_sessions(db, client_id)
    return [SessionOut.model_validate(session, from_attributes=True) for session in sessions]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: str,
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> SessionOut:
    session = await session_service.get_session(db, session_id, client_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut.model_validate(session, from_attributes=True)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(
    session_id: str,
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[MessageOut]:
    session = await session_service.get_session(db, session_id, client_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await session_service.list_messages(db, session_id, client_id)
    return [MessageOut.model_validate(message, from_attributes=True) for message in messages]


@router.post("/sessions/{session_id}/messages", response_model=MessageRunResponse)
async def submit_user_message(
    session_id: str,
    payload: MessageCreateRequest,
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> MessageRunResponse:
    run_id, assistant_response = await chat_service.process_user_message(db, session_id, payload, client_id)
    return MessageRunResponse(run_id=run_id, response=assistant_response)


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(
    run_id: str,
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> RunOut:
    run = await chat_service.get_run(db, run_id, client_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut.model_validate(run, from_attributes=True)


@router.get("/runs/{run_id}/steps", response_model=list[RunStepOut])
async def get_run_steps(
    run_id: str,
    client_id: str = Depends(get_anonymous_client_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[RunStepOut]:
    steps = await chat_service.list_run_steps(db, run_id, client_id)
    return [RunStepOut.model_validate(step, from_attributes=True) for step in steps]
