from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    session_id: str
    run_id: str
    user_message_id: str
    user_question: str
    session_context: dict[str, Any]
    parsed_query: dict[str, Any]
    pending_tasks: list[dict[str, Any]]
    completed_tasks: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    evidence_items: list[dict[str, Any]]
    unresolved_gaps: list[str]
    iteration: int
    step_trace: list[dict[str, Any]]
    emit_progress: Any
    draft_response: dict[str, Any]
    verification_result: dict[str, Any]
    final_response: dict[str, Any]
