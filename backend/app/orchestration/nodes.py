from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.agents.specialists import RetrievalSpecialist
from app.core.config import get_settings
from app.schemas.common import (
    AssistantResponse,
    Citation,
    EvidenceAssessmentResult,
    EvidenceCoverageDecision,
    EvidenceItem,
    EvidencePlan,
    NormalizedQuery,
    RetrievalSpec,
    SpecialistTask,
    VerificationResult,
)
from app.services.llm_service import get_llm_service

settings = get_settings()
llm_service = get_llm_service()

PROGRESS_MESSAGES = {
    "load_session_context": "Loading session context.",
    "normalize_query": "Normalizing the query.",
    "plan_evidence": "Planning evidence retrieval.",
    "dispatch_specialists": "Retrieval pass completed.",
    "aggregate_evidence": "Aggregating evidence.",
    "assess_coverage": "Checking evidence coverage.",
    "synthesize_answer": "Drafting answer from evidence.",
    "verify_answer": "Verifying answer support.",
    "finalize_response": "Finalizing response.",
}


def _emit_progress(state: dict, event: dict) -> None:
    emitter = state.get("emit_progress")
    if emitter:
        emitter(event)


def _trace(state: dict, node_name: str, input_payload: dict, output_payload: dict) -> list[dict]:
    current = list(state.get("step_trace", []))
    step = {
        "node_name": node_name,
        "status": "completed",
        "input": input_payload,
        "output": output_payload,
    }
    current.append(step)
    _emit_progress(
        state,
        {
            "type": "progress",
            "node_name": node_name,
            "step_order": len(current),
            "message": PROGRESS_MESSAGES.get(node_name, node_name.replace("_", " ").title()),
        },
    )
    return current


def _retrieval_specs_to_tasks(retrieval_specs: list[RetrievalSpec]) -> list[SpecialistTask]:
    tasks: list[SpecialistTask] = []
    for spec in retrieval_specs[: settings.max_specialist_tasks]:
        tasks.append(
            SpecialistTask(
                task_id=str(uuid4()),
                agent_type=spec.lane,
                objective=spec.objective,
                query_text=spec.query_text,
                source_query=spec.source_query,
                rationale=spec.rationale,
                focus_terms=spec.focus_terms,
                must_concepts=spec.must_concepts,
                supporting_concepts=spec.supporting_concepts,
                population_terms=spec.population_terms,
                intervention_terms=spec.intervention_terms,
                question_focus_terms=spec.question_focus_terms,
                exclude_concepts=spec.exclude_concepts,
                preferred_evidence_types=spec.preferred_evidence_types,
                recency_years=spec.recency_years,
                priority=spec.priority,
                desired_result_count=spec.desired_result_count,
                depends_on=spec.depends_on,
            )
        )
    return tasks


def _existing_task_signature(task: SpecialistTask) -> tuple[str, str]:
    signature_parts = [
        task.query_text.strip().lower(),
        "|".join(term.lower() for term in task.must_concepts),
        "|".join(term.lower() for term in task.population_terms),
        "|".join(term.lower() for term in task.intervention_terms),
        "|".join(term.lower() for term in task.question_focus_terms),
        (task.source_query or "").strip().lower(),
    ]
    return task.agent_type, "||".join(part for part in signature_parts if part)


def load_session_context(state: dict) -> dict:
    session_context = state.get("session_context", {})
    output = {"session_context": session_context}
    return {
        **output,
        "step_trace": _trace(state, "load_session_context", {}, output),
    }


def normalize_query(state: dict) -> dict:
    question = state["user_question"].strip()
    session_context = state.get("session_context", {})
    normalized_query = llm_service.normalize_query(question=question, session_context=session_context)
    if normalized_query is None:
        response = AssistantResponse(
            status="abstained",
            abstention_class="semantic_layer_unavailable",
            abstention_reason="Query normalization did not produce a valid structured result.",
            evidence_summary=[],
            limitations=["The semantic layer did not return a valid normalized query."],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"final_response": response.model_dump(mode="json")}
        return {
            **output,
            "step_trace": _trace(state, "normalize_query", {"question": question}, output),
        }
    output = {"normalized_query": normalized_query.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "normalize_query", {"question": question}, output),
    }


def plan_evidence(state: dict) -> dict:
    normalized_query = NormalizedQuery.model_validate(state["normalized_query"])
    session_context = state.get("session_context", {})

    if not normalized_query.scope.in_scope:
        response = AssistantResponse(
            status="abstained",
            abstention_class="out_of_scope",
            abstention_reason=normalized_query.scope.reason
            or "This question is outside the configured medical evidence scope.",
            evidence_summary=[],
            limitations=["Current scope is limited to clinical evidence retrieval and synthesis."],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"final_response": response.model_dump(mode="json"), "pending_tasks": []}
        return {
            **output,
            "step_trace": _trace(state, "plan_evidence", {"normalized_query": state["normalized_query"]}, output),
        }

    if normalized_query.needs_clarification:
        response = AssistantResponse(
            status="needs_clarification",
            clarification_question=normalized_query.clarification_question,
            evidence_summary=[],
            limitations=normalized_query.ambiguity_notes,
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"final_response": response.model_dump(mode="json"), "pending_tasks": []}
        return {
            **output,
            "step_trace": _trace(state, "plan_evidence", {"normalized_query": state["normalized_query"]}, output),
        }

    evidence_plan = llm_service.plan_evidence(normalized_query=normalized_query, session_context=session_context)
    if evidence_plan is None or not evidence_plan.retrieval_specs:
        response = AssistantResponse(
            status="abstained",
            abstention_class="planning_failure",
            abstention_reason="The planner could not produce a usable evidence-gathering plan.",
            evidence_summary=[],
            limitations=["The semantic planner returned no retrieval specifications."],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"final_response": response.model_dump(mode="json"), "pending_tasks": []}
        return {
            **output,
            "step_trace": _trace(state, "plan_evidence", {"normalized_query": state["normalized_query"]}, output),
        }

    tasks = _retrieval_specs_to_tasks(evidence_plan.retrieval_specs)
    output = {
        "evidence_plan": evidence_plan.model_dump(mode="json"),
        "pending_tasks": [task.model_dump(mode="json") for task in tasks],
        "iteration": int(state.get("iteration", 0)),
    }
    return {
        **output,
        "step_trace": _trace(state, "plan_evidence", {"normalized_query": state["normalized_query"]}, output),
    }


async def dispatch_specialists(state: dict, specialists: dict[str, RetrievalSpecialist]) -> dict:
    normalized_query = NormalizedQuery.model_validate(state["normalized_query"])
    pending_tasks = [SpecialistTask.model_validate(task) for task in state.get("pending_tasks", [])]

    async def run_task(task: SpecialistTask) -> dict:
        specialist = specialists[task.agent_type]
        _emit_progress(
            state,
            {
                "type": "progress",
                "agent_type": task.agent_type,
                "connector": specialist.connector.connector_name,
                "message": f"{task.agent_type.replace('_', ' ').title()} agent querying {specialist.connector.connector_name}.",
            },
        )
        sources, evidence = await specialist.run(normalized_query, task)
        _emit_progress(
            state,
            {
                "type": "progress",
                "agent_type": task.agent_type,
                "connector": specialist.connector.connector_name,
                "message": f"{task.agent_type.replace('_', ' ').title()} agent returned {len(evidence)} evidence item{'s' if len(evidence) != 1 else ''}.",
            },
        )
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


def assess_coverage(state: dict) -> dict:
    normalized_query = NormalizedQuery.model_validate(state["normalized_query"])
    evidence_plan = EvidencePlan.model_validate(state["evidence_plan"])
    evidence_items = [EvidenceItem.model_validate(item) for item in state.get("evidence_items", [])]
    completed_tasks = [SpecialistTask.model_validate(result["task"]) for result in state.get("completed_tasks", [])]
    completed_lanes = [task.agent_type for task in completed_tasks]
    iteration = int(state.get("iteration", 0))

    coverage = llm_service.assess_coverage(
        normalized_query=normalized_query,
        evidence_plan=evidence_plan,
        evidence_items=evidence_items,
        completed_lanes=completed_lanes,
        iteration=iteration,
    )
    if coverage is None:
        coverage = EvidenceCoverageDecision(
            answerable_now=bool(evidence_items),
            needs_follow_up=False,
            rationale="Coverage assessment did not return a valid structured result.",
            remaining_gaps=[] if evidence_items else ["no_retrieved_evidence"],
            follow_up_specs=[],
        )

    existing_signatures = {_existing_task_signature(task) for task in completed_tasks}
    follow_up_tasks: list[SpecialistTask] = []
    for spec in coverage.follow_up_specs:
        candidate = SpecialistTask(
            task_id=str(uuid4()),
            agent_type=spec.lane,
            objective=spec.objective,
            query_text=spec.query_text,
            source_query=spec.source_query,
            rationale=spec.rationale,
            focus_terms=spec.focus_terms,
            must_concepts=spec.must_concepts,
            supporting_concepts=spec.supporting_concepts,
            population_terms=spec.population_terms,
            intervention_terms=spec.intervention_terms,
            question_focus_terms=spec.question_focus_terms,
            exclude_concepts=spec.exclude_concepts,
            preferred_evidence_types=spec.preferred_evidence_types,
            recency_years=spec.recency_years,
            priority=spec.priority,
            desired_result_count=spec.desired_result_count,
            depends_on=spec.depends_on,
        )
        signature = _existing_task_signature(candidate)
        if signature not in existing_signatures:
            follow_up_tasks.append(candidate)
            existing_signatures.add(signature)

    output = {
        "coverage_decision": coverage.model_dump(mode="json"),
        "unresolved_gaps": coverage.remaining_gaps,
        "pending_tasks": [task.model_dump(mode="json") for task in follow_up_tasks],
        "iteration": iteration + 1,
    }
    return {
        **output,
        "step_trace": _trace(
            state,
            "assess_coverage",
            {"completed_lanes": completed_lanes},
            {
                "answerable_now": coverage.answerable_now,
                "followup_task_count": len(follow_up_tasks),
                "remaining_gaps": coverage.remaining_gaps,
            },
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


def _has_recent_evidence(evidence_items: list[EvidenceItem], years: int) -> bool:
    recency_floor = datetime.now(UTC) - timedelta(days=365 * years)
    for item in evidence_items:
        if item.publication_date and datetime.combine(item.publication_date, datetime.min.time(), tzinfo=UTC) >= recency_floor:
            return True
    return False


def _apply_llm_evidence_assessment(
    normalized_query: NormalizedQuery,
    evidence_plan: EvidencePlan,
    evidence_items: list[EvidenceItem],
) -> list[EvidenceItem]:
    assessment = llm_service.assess_evidence(
        normalized_query=normalized_query,
        evidence_plan=evidence_plan,
        evidence_items=evidence_items,
    )
    if assessment is None:
        return evidence_items

    assessment_by_id = {item.evidence_id: item for item in assessment.items}
    updated: list[EvidenceItem] = []
    for item in evidence_items:
        assessed = assessment_by_id.get(item.evidence_id)
        if assessed is None:
            updated.append(item)
            continue
        updated.append(
            item.model_copy(
                update={
                    "question_role": assessed.question_role,
                    "claim_type": assessed.claim_type,
                    "applicability": assessed.applicability,
                    "supports_question_dimensions": assessed.supports_question_dimensions,
                    "semantic_relevance": assessed.semantic_relevance,
                    "include_in_answer": assessed.include_in_answer,
                    "assessment_summary": assessed.assessment_summary,
                }
            )
        )
    return updated


def _order_evidence_items(normalized_query: NormalizedQuery, evidence_plan: EvidencePlan, evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    assessed_items = _apply_llm_evidence_assessment(normalized_query, evidence_plan, evidence_items[:8])
    if len(evidence_items) > 8:
        assessed_items.extend(evidence_items[8:])
    return sorted(
        assessed_items,
        key=lambda item: (
            1 if item.include_in_answer else 0,
            item.semantic_relevance or 0,
            item.source_priority,
            item.publication_date.toordinal() if item.publication_date else 0,
        ),
        reverse=True,
    )


def _select_synthesis_evidence(evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    included = [item for item in evidence_items if item.include_in_answer is not False]
    return (included or evidence_items)[:6]


def _soft_verification_limitations(unsupported_claims: list[str]) -> list[str]:
    return [claim for claim in unsupported_claims if claim]


def _apply_verification_guardrails(
    normalized_query: NormalizedQuery,
    evidence_plan: EvidencePlan,
    draft: AssistantResponse,
    verification: VerificationResult,
    evidence_items: list[EvidenceItem],
) -> VerificationResult:
    if draft.status != "answered":
        return verification

    unsupported = list(verification.unsupported_claims)
    abstention_class = verification.abstention_class
    abstention_reason = verification.abstention_reason

    if not draft.citations:
        unsupported.append("The drafted answer does not include citations.")
        abstention_class = abstention_class or "insufficient_evidence"
        abstention_reason = abstention_reason or "The answer draft does not contain supporting citations."

    if not evidence_items:
        unsupported.append("No evidence items were available for verification.")
        abstention_class = abstention_class or "insufficient_evidence"
        abstention_reason = abstention_reason or "No supporting evidence was available."

    if normalized_query.recency_focus and not _has_recent_evidence(evidence_items, settings.recency_guardrail_years):
        unsupported.append("The retrieved evidence is not recent enough for a recency-sensitive question.")
        abstention_class = "recency_gap"
        abstention_reason = "The available evidence does not include sufficiently recent sources for a recency-sensitive question."

    if verification.status == "pass" and abstention_class is None:
        return VerificationResult(
            status="pass",
            supported_claims=verification.supported_claims,
            unsupported_claims=sorted(set(unsupported)),
            conflicts=verification.conflicts,
            abstention_class=None,
            abstention_reason=None,
        )

    if verification.status == "clarify" and abstention_class is None:
        return VerificationResult(
            status="clarify",
            supported_claims=verification.supported_claims,
            unsupported_claims=sorted(set(unsupported)),
            conflicts=verification.conflicts,
            abstention_class=None,
            abstention_reason=None,
        )

    final_class = abstention_class or ("insufficient_evidence" if unsupported else verification.abstention_class)
    final_reason = abstention_reason or verification.abstention_reason or "Unable to verify a safe grounded answer."
    return VerificationResult(
        status="abstain",
        supported_claims=verification.supported_claims,
        unsupported_claims=sorted(set(unsupported)),
        conflicts=verification.conflicts,
        abstention_class=final_class,
        abstention_reason=final_reason,
    )


def synthesize_answer(state: dict) -> dict:
    evidence_items = [EvidenceItem.model_validate(item) for item in state.get("evidence_items", [])]
    normalized_query = NormalizedQuery.model_validate(state["normalized_query"])
    evidence_plan = EvidencePlan.model_validate(state["evidence_plan"])
    ordered_evidence = _order_evidence_items(normalized_query, evidence_plan, evidence_items)
    if not ordered_evidence:
        response = AssistantResponse(
            status="abstained",
            abstention_class="insufficient_evidence",
            abstention_reason="No supporting evidence could be retrieved from the currently configured sources.",
            limitations=["No evidence items were available after retrieval."],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"draft_response": response.model_dump(mode="json"), "evidence_items": []}
        return {
            **output,
            "step_trace": _trace(state, "synthesize_answer", {"evidence_count": 0}, output),
        }

    citations: list[Citation] = []
    top_evidence = _select_synthesis_evidence(ordered_evidence)
    for index, item in enumerate(top_evidence[:4], start=1):
        citations.append(
            Citation(
                label=str(index),
                source_id=item.source_id,
                title=item.title,
                url=item.url,
                publication_date=item.publication_date,
                source_type=item.source_type,
                publisher=item.publisher,
                snippet=item.key_claim,
            )
        )

    llm_draft = llm_service.synthesize_answer(
        normalized_query=normalized_query,
        evidence_plan=evidence_plan,
        evidence_items=top_evidence,
        citations=citations,
    )
    if llm_draft is not None:
        response = AssistantResponse(
            status="answered",
            answer=llm_draft.answer,
            evidence_summary=llm_draft.evidence_summary,
            evidence_strength=llm_draft.evidence_strength,
            limitations=llm_draft.limitations,
            citations=citations,
            evidence_items=top_evidence,
            last_literature_check_at=datetime.now(UTC),
        )
        output = {
            "draft_response": response.model_dump(mode="json"),
            "evidence_items": [item.model_dump(mode="json") for item in ordered_evidence],
        }
        return {
            **output,
            "step_trace": _trace(
                state,
                "synthesize_answer",
                {"evidence_count": len(ordered_evidence), "mode": "gemini" if llm_service.enabled else settings.llm_mode},
                {"citation_count": len(citations)},
            ),
        }

    lead_item = top_evidence[0]
    response = AssistantResponse(
        status="answered",
        answer=lead_item.key_claim,
        evidence_summary=[item.key_claim for item in top_evidence[:3]],
        evidence_strength=(
            "high"
            if any(item.evidence_strength == "high" for item in top_evidence)
            else "moderate"
            if any(item.evidence_strength == "moderate" for item in top_evidence)
            else "low"
        ),
        limitations=["Semantic synthesis fallback is active; production-quality phrasing requires Gemini."],
        citations=citations,
        evidence_items=top_evidence,
        last_literature_check_at=datetime.now(UTC),
    )
    output = {
        "draft_response": response.model_dump(mode="json"),
        "evidence_items": [item.model_dump(mode="json") for item in ordered_evidence],
    }
    return {
        **output,
        "step_trace": _trace(
            state,
            "synthesize_answer",
            {"evidence_count": len(ordered_evidence), "mode": settings.llm_mode},
            {"citation_count": len(citations)},
        ),
    }


def verify_answer(state: dict) -> dict:
    draft = AssistantResponse.model_validate(state["draft_response"])
    normalized_query = NormalizedQuery.model_validate(state["normalized_query"])
    evidence_plan = EvidencePlan.model_validate(state["evidence_plan"])
    evidence_items = [EvidenceItem.model_validate(item) for item in state.get("evidence_items", [])]
    llm_verification = llm_service.verify_answer(
        normalized_query=normalized_query,
        evidence_plan=evidence_plan,
        draft_response=draft,
        evidence_items=evidence_items[:6],
    )
    if llm_verification is None:
        llm_verification = VerificationResult(
            status="pass" if draft.citations else "abstain",
            supported_claims=[],
            unsupported_claims=[] if draft.citations else ["The draft answer did not contain citations."],
            conflicts=[],
            abstention_class=None if draft.citations else "insufficient_evidence",
            abstention_reason=None if draft.citations else "Draft answer failed basic citation support checks.",
        )

    guarded = _apply_verification_guardrails(normalized_query, evidence_plan, draft, llm_verification, evidence_items)
    output = {"verification_result": guarded.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(
            state,
            "verify_answer",
            {"draft_status": draft.status, "mode": "gemini" if llm_service.enabled else settings.llm_mode},
            output,
        ),
    }


def finalize_response(state: dict) -> dict:
    if state.get("final_response"):
        final = AssistantResponse.model_validate(state["final_response"])
    else:
        draft = AssistantResponse.model_validate(state["draft_response"])
        verification = VerificationResult.model_validate(state["verification_result"])
        if verification.status == "pass":
            merged_limitations = list(dict.fromkeys(draft.limitations + _soft_verification_limitations(verification.unsupported_claims)))
            final = draft.model_copy(update={"limitations": merged_limitations})
        elif verification.status == "clarify":
            final = AssistantResponse(
                status="needs_clarification",
                clarification_question=draft.clarification_question,
                evidence_summary=draft.evidence_summary,
                limitations=draft.limitations,
                citations=draft.citations,
                evidence_items=draft.evidence_items,
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
                evidence_items=draft.evidence_items,
                last_literature_check_at=datetime.now(UTC),
            )

    output = {"final_response": final.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "finalize_response", {}, output),
    }
