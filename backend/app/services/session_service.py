from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import ChatMessage, ChatSession, Run, RunStep
from app.schemas.session import MessageCreateRequest


async def create_session(session: AsyncSession, owner_id: str, title: str | None = None) -> ChatSession:
    chat_session = ChatSession(owner_id=owner_id, title=title)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def get_session(session: AsyncSession, session_id: str, owner_id: str) -> ChatSession | None:
    result = await session.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(session: AsyncSession, owner_id: str) -> list[ChatSession]:
    result = await session.execute(
        select(ChatSession).where(ChatSession.owner_id == owner_id).order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars())


async def list_messages(session: AsyncSession, session_id: str, owner_id: str) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatMessage.session_id == session_id, ChatSession.owner_id == owner_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars())


async def create_message(
    session: AsyncSession,
    session_id: str,
    payload: MessageCreateRequest,
    owner_id: str,
    metadata_json: dict | None = None,
) -> ChatMessage:
    chat_session = await get_session(session, session_id, owner_id)
    message = ChatMessage(
        session_id=session_id,
        role=payload.role,
        content=payload.content,
        metadata_json=metadata_json or {},
    )
    if chat_session is not None:
        chat_session.updated_at = datetime.now(UTC)
        if not chat_session.title and payload.role == "user":
            title = payload.content.strip().replace("\n", " ")
            chat_session.title = title[:72] + ("…" if len(title) > 72 else "")
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def create_run(session: AsyncSession, session_id: str, message_id: str | None) -> Run:
    run = Run(session_id=session_id, message_id=message_id, status="running")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def update_run(
    session: AsyncSession,
    run: Run,
    *,
    status: str,
    iteration_count: int,
    final_status: str,
    final_response_json: dict,
) -> Run:
    run.status = status
    run.iteration_count = iteration_count
    run.final_status = final_status
    run.final_response_json = final_response_json
    await session.commit()
    await session.refresh(run)
    return run


async def update_session_context(
    session: AsyncSession,
    session_id: str,
    owner_id: str,
    context_json: dict,
) -> ChatSession | None:
    chat_session = await get_session(session, session_id, owner_id)
    if chat_session is None:
        return None
    chat_session.context_json = context_json
    chat_session.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def store_run_steps(session: AsyncSession, run_id: str, step_trace: list[dict]) -> None:
    for index, step in enumerate(step_trace, start=1):
        session.add(
            RunStep(
                run_id=run_id,
                node_name=step["node_name"],
                step_order=index,
                status=step.get("status", "completed"),
                input_json=step.get("input", {}),
                output_json=step.get("output", {}),
            )
        )
    await session.commit()
