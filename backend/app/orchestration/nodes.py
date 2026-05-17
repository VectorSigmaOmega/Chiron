from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.agents.specialists import RetrievalSpecialist
from app.core.config import get_settings
from app.schemas.common import (
    AssistantResponse,
    Citation,
    EntityRef,
    InformationNeed,
    ParsedQuery,
    SpecialistTask,
    VerificationResult,
    VerifiedClaim,
)

settings = get_settings()


def _trace(state: dict, node_name: str, input_payload: dict, output_payload: dict) -> list[dict]:
    current = list(state.get("step_trace", []))
    current.append(
        {
            "node_name": node_name,
            "status": "completed",
            "input": input_payload,
            "output": output_payload,
        }
    )
    return current


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def load_session_context(state: dict) -> dict:
    session_context = state.get("session_context", {})
    output = {"session_context": session_context}
    return {
        **output,
        "step_trace": _trace(state, "load_session_context", {}, output),
    }


def parse_query(state: dict) -> dict:
    question = state["user_question"].strip()
    lowered = question.lower()
    entities: list[EntityRef] = []
    if "tuberculosis" in lowered or "tb" in lowered:
        entities.append(EntityRef(name="drug-resistant tuberculosis", kind="condition"))
    if "bedaquiline" in lowered:
        entities.append(EntityRef(name="bedaquiline", kind="drug"))

    pregnancy_status = "pregnant" if "pregnan" in lowered else None
    recency_required = _contains_any(lowered, ["latest", "recent", "current"])
    needs_safety = _contains_any(lowered, ["safety", "side effect", "adverse", "contraindication"])
    needs_trials = _contains_any(lowered, ["trial", "experimental", "investigational"]) or recency_required

    missing_dimensions: list[str] = []
    clarification_question: str | None = None
    needs_clarification = False

    if "pneumonia" in lowered and not _contains_any(
        lowered, ["adult", "child", "pregnan", "outpatient", "inpatient"]
    ):
        needs_clarification = True
        missing_dimensions = ["population", "care_setting"]
        clarification_question = (
            "Can you specify the patient population and care setting, for example adult or child, "
            "and inpatient or outpatient?"
        )

    information_needs = [InformationNeed(name="literature", reason="baseline evidence review")]
    if _contains_any(lowered, ["treatment", "management", "guideline"]):
        information_needs.append(
            InformationNeed(name="guidelines", reason="treatment questions should check guidance first")
        )
    if needs_safety:
        information_needs.append(
            InformationNeed(name="drug_safety", reason="question explicitly asks for safety concerns")
        )
    if needs_trials:
        information_needs.append(
            InformationNeed(name="trials", reason="question requests current or emerging evidence")
        )

    parsed = ParsedQuery(
        original_question=question,
        rewritten_question=question,
        entities=entities,
        population="pregnancy" if pregnancy_status else None,
        setting=None,
        pregnancy_status=pregnancy_status,
        recency_required=recency_required,
        missing_dimensions=missing_dimensions,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        information_needs=information_needs,
    )
    output = {"parsed_query": parsed.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "parse_query", {"question": question}, output),
    }


def clarify_or_plan(state: dict) -> dict:
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    tasks: list[SpecialistTask] = []
    if parsed_query.needs_clarification:
        response = AssistantResponse(
            status="needs_clarification",
            clarification_question=parsed_query.clarification_question,
            evidence_summary=[],
            limitations=[f"Missing dimensions: {', '.join(parsed_query.missing_dimensions)}"],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"final_response": response.model_dump(mode="json"), "pending_tasks": []}
        return {
            **output,
            "step_trace": _trace(state, "clarify_or_plan", {"parsed_query": state["parsed_query"]}, output),
        }

    lowered = parsed_query.original_question.lower()
    task_specs: list[tuple[str, str, list[str]]] = []
    if _contains_any(lowered, ["treatment", "management", "guideline"]):
        task_specs.append(("guideline", "Retrieve guideline-backed recommendations", []))
    task_specs.append(("literature", "Search literature for supporting evidence", []))
    if _contains_any(lowered, ["safety", "side effect", "adverse", "contraindication"]):
        task_specs.append(("drug_safety", "Look up major safety concerns", []))
    if parsed_query.recency_required or _contains_any(lowered, ["trial", "experimental", "investigational"]):
        task_specs.append(("trials", "Check trial and emerging evidence", []))

    for agent_type, goal, depends_on in task_specs[: settings.max_specialist_tasks]:
        tasks.append(
            SpecialistTask(
                task_id=str(uuid4()),
                agent_type=agent_type,
                goal=goal,
                subquery=parsed_query.rewritten_question,
                depends_on=depends_on,
                focus_entities=[entity.name for entity in parsed_query.entities],
            )
        )

    output = {
        "pending_tasks": [task.model_dump(mode="json") for task in tasks],
        "iteration": int(state.get("iteration", 0)),
    }
    return {
        **output,
        "step_trace": _trace(state, "clarify_or_plan", {"parsed_query": state["parsed_query"]}, output),
    }


async def dispatch_specialists(state: dict, specialists: dict[str, RetrievalSpecialist]) -> dict:
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    pending_tasks = [SpecialistTask.model_validate(task) for task in state.get("pending_tasks", [])]

    async def run_task(task: SpecialistTask) -> dict:
        specialist = specialists[task.agent_type]
        sources, evidence = await specialist.run(parsed_query, task)
        return {
            "task": task.model_dump(mode="json"),
            "sources": [source.model_dump(mode="json") for source in sources],
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }

    results = await asyncio.gather(*(run_task(task) for task in pending_tasks), return_exceptions=False)
    completed_tasks = list(state.get("completed_tasks", [])) + results
    aggregated_sources = list(state.get("sources", []))
    aggregated_evidence = list(state.get("evidence_items", []))
    for result in results:
        aggregated_sources.extend(result["sources"])
        aggregated_evidence.extend(result["evidence"])

    output = {
        "completed_tasks": completed_tasks,
        "sources": aggregated_sources,
        "evidence_items": aggregated_evidence,
        "pending_tasks": [],
    }
    return {
        **output,
        "step_trace": _trace(
            state,
            "dispatch_specialists",
            {"task_count": len(pending_tasks)},
            {"completed_task_count": len(completed_tasks), "evidence_count": len(aggregated_evidence)},
        ),
    }


def aggregate_evidence(state: dict) -> dict:
    evidence_items = list(state.get("evidence_items", []))
    source_ids = {item["source_id"] for item in evidence_items}
    output = {"evidence_items": evidence_items, "source_count": len(source_ids)}
    return {
        **output,
        "step_trace": _trace(state, "aggregate_evidence", {}, output),
    }


def assess_gaps(state: dict) -> dict:
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    completed_tasks = list(state.get("completed_tasks", []))
    completed_agent_types = {task["task"]["agent_type"] for task in completed_tasks}
    evidence_items = state.get("evidence_items", [])
    followup_entities: list[str] = []
    for item in evidence_items:
        for entity in item.get("extracted_entities", []):
            if entity and entity not in followup_entities:
                followup_entities.append(entity)
    if not followup_entities:
        followup_entities = [entity.name for entity in parsed_query.entities]
    unresolved_gaps: list[str] = []
    followups: list[SpecialistTask] = []
    next_iteration = int(state.get("iteration", 0)) + 1

    lowered = parsed_query.original_question.lower()
    if _contains_any(lowered, ["safety", "side effect", "adverse"]) and "drug_safety" not in completed_agent_types:
        followups.append(
            SpecialistTask(
                task_id=str(uuid4()),
                agent_type="drug_safety",
                goal="Follow up on safety-specific evidence",
                subquery=parsed_query.rewritten_question,
                depends_on=[],
                focus_entities=followup_entities,
            )
        )
    if parsed_query.recency_required and "trials" not in completed_agent_types:
        followups.append(
            SpecialistTask(
                task_id=str(uuid4()),
                agent_type="trials",
                goal="Follow up on latest or emerging evidence",
                subquery=parsed_query.rewritten_question,
                depends_on=[],
                focus_entities=followup_entities,
            )
        )

    if not evidence_items:
        unresolved_gaps.append("no_retrieved_evidence")

    output = {
        "unresolved_gaps": unresolved_gaps,
        "pending_tasks": [task.model_dump(mode="json") for task in followups],
        "iteration": next_iteration,
    }
    return {
        **output,
        "step_trace": _trace(
            state,
            "assess_gaps",
            {"completed_agent_types": sorted(completed_agent_types)},
            {"followup_task_count": len(followups), "unresolved_gaps": unresolved_gaps},
        ),
    }


def should_replan(state: dict) -> str:
    if state.get("final_response"):
        return "finalize"
    pending_tasks = state.get("pending_tasks", [])
    iteration = int(state.get("iteration", 0))
    if pending_tasks and iteration < settings.max_iterations:
        return "dispatch_specialists"
    return "synthesize_answer"


def synthesize_answer(state: dict) -> dict:
    evidence_items = state.get("evidence_items", [])
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    if not evidence_items:
        response = AssistantResponse(
            status="abstained",
            abstention_class="insufficient_evidence",
            abstention_reason="No supporting evidence could be retrieved from the currently configured sources.",
            limitations=["Backend scaffold is running, but live source coverage is still limited."],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"draft_response": response.model_dump(mode="json")}
        return {
            **output,
            "step_trace": _trace(state, "synthesize_answer", {"evidence_count": 0}, output),
        }

    citations: list[Citation] = []
    evidence_summary: list[str] = []
    answer_lines: list[str] = []
    safety_notes: list[str] = []
    for index, item in enumerate(evidence_items[:4], start=1):
        citations.append(
            Citation(
                label=str(index),
                source_id=item["source_id"],
                title=item["title"],
                url=item["url"],
                publication_date=item.get("publication_date"),
            )
        )
        evidence_summary.append(item["key_claim"])
        if item["safety_notes"]:
            safety_notes.extend(item["safety_notes"])

    if parsed_query.pregnancy_status:
        answer_lines.append(
            "Current scaffold evidence suggests treatment decisions should be individualized with specialist input because pregnancy-specific evidence remains limited."
        )
    answer_lines.append("Most available evidence should be interpreted alongside guideline and safety-specific review.")
    if safety_notes:
        answer_lines.append(f"Key safety considerations mentioned in retrieved evidence include {', '.join(sorted(set(safety_notes)))}.")

    response = AssistantResponse(
        status="answered",
        answer=" ".join(answer_lines),
        evidence_summary=evidence_summary,
        evidence_strength="moderate",
        limitations=[
            "This deployable MVP currently mixes mock retrieval with real orchestration and should not be treated as production clinical decision support."
        ],
        citations=citations,
        last_literature_check_at=datetime.now(UTC),
    )
    output = {"draft_response": response.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(
            state,
            "synthesize_answer",
            {"evidence_count": len(evidence_items)},
            {"citation_count": len(citations)},
        ),
    }


def verify_answer(state: dict) -> dict:
    draft = AssistantResponse.model_validate(state["draft_response"])
    evidence_items = state.get("evidence_items", [])
    if draft.status != "answered":
        verification = VerificationResult(
            status="abstain" if draft.status == "abstained" else "clarify",
            supported_claims=[],
            unsupported_claims=[],
            conflicts=[],
            abstention_class=draft.abstention_class,
            abstention_reason=draft.abstention_reason,
        )
    else:
        supported = [
            VerifiedClaim(
                claim_text=item["key_claim"],
                supporting_source_ids=[item["source_id"]],
            )
            for item in evidence_items[:3]
        ]
        unsupported_claims: list[str] = []
        if not draft.citations:
            unsupported_claims.append("draft_answer_missing_citations")
        if draft.last_literature_check_at and draft.last_literature_check_at < datetime.now(UTC) - timedelta(days=365 * 4):
            unsupported_claims.append("stale_literature_check")

        verification = VerificationResult(
            status="pass" if not unsupported_claims else "abstain",
            supported_claims=supported,
            unsupported_claims=unsupported_claims,
            conflicts=[],
            abstention_class="insufficient_evidence" if unsupported_claims else None,
            abstention_reason="Draft answer failed basic support checks." if unsupported_claims else None,
        )

    output = {"verification_result": verification.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "verify_answer", {"draft_status": draft.status}, output),
    }


def finalize_response(state: dict) -> dict:
    if state.get("final_response"):
        final = AssistantResponse.model_validate(state["final_response"])
    else:
        draft = AssistantResponse.model_validate(state["draft_response"])
        verification = VerificationResult.model_validate(state["verification_result"])
        if verification.status == "pass":
            final = draft
        elif verification.status == "clarify":
            final = AssistantResponse(
                status="needs_clarification",
                clarification_question=draft.clarification_question,
                evidence_summary=draft.evidence_summary,
                limitations=draft.limitations,
                last_literature_check_at=datetime.now(UTC),
            )
        else:
            final = AssistantResponse(
                status="abstained",
                abstention_class=verification.abstention_class or "insufficient_evidence",
                abstention_reason=verification.abstention_reason or "Unable to verify a safe grounded answer.",
                evidence_summary=draft.evidence_summary,
                limitations=draft.limitations,
                citations=draft.citations,
                last_literature_check_at=datetime.now(UTC),
            )

    output = {"final_response": final.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "finalize_response", {}, output),
    }
