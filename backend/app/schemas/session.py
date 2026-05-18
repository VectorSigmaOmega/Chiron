from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import AssistantResponse


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageCreateRequest(BaseModel):
    role: str = "user"
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    metadata_json: dict
    created_at: datetime


class MessageRunResponse(BaseModel):
    run_id: str
    response: AssistantResponse


class RunStartResponse(BaseModel):
    run_id: str


class RunOut(BaseModel):
    id: str
    session_id: str
    message_id: str | None = None
    status: str
    iteration_count: int
    final_status: str | None = None
    final_response_json: dict
    created_at: datetime
    updated_at: datetime


class RunStepOut(BaseModel):
    id: str
    run_id: str
    node_name: str
    step_order: int
    status: str
    input_json: dict
    output_json: dict
    created_at: datetime
