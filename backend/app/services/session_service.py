from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import ChatMessage, ChatSession, Run, RunStep
from app.schemas.session import MessageCreateRequest


async def create_session(session: AsyncSession, title: str | None = None) -> ChatSession:
    chat_session = ChatSession(title=title)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def get_session(session: AsyncSession, session_id: str) -> ChatSession | None:
    return await session.get(ChatSession, session_id)


async def list_messages(session: AsyncSession, session_id: str) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars())


async def create_message(
    session: AsyncSession,
    session_id: str,
    payload: MessageCreateRequest,
    metadata_json: dict | None = None,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id,
        role=payload.role,
        content=payload.content,
        metadata_json=metadata_json or {},
    )
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
