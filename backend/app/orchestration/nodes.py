from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.agents.specialists import RetrievalSpecialist
from app.core.config import get_settings
from app.schemas.common import (
    AssistantResponse,
    Citation,
    EvidenceItem,
    EntityRef,
    InformationNeed,
    ParsedQuery,
    SpecialistTask,
    VerificationResult,
    VerifiedClaim,
)
from app.services.llm_service import get_llm_service

settings = get_settings()
llm_service = get_llm_service()


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


OUT_OF_SCOPE_NEEDLES = [
    "billing",
    "cpt code",
    "cpt",
    "icd",
    "hcpcs",
    "prior auth",
    "prior authorization",
    "insurance",
    "coverage",
    "copay",
    "co-pay",
    "reimbursement",
    "claim denial",
]

MODIFIER_ALIASES: dict[str, list[str]] = {
    "pregnancy": ["pregnan", "maternal"],
    "hiv": ["hiv", "hiv-positive", "hiv positive"],
    "aids": ["aids"],
    "diabetes": ["diabetes", "diabetic"],
    "renal_impairment": ["renal impairment", "kidney disease", "renal failure", "ckd"],
    "hepatic_impairment": ["hepatic impairment", "liver disease", "liver failure", "cirrhosis"],
    "pediatric": ["pediatric", "paediatric", "child", "children"],
    "adult": ["adult", "adults"],
    "geriatric": ["elderly", "older adult", "geriatric"],
    "immunocompromised": ["immunocompromised", "immunosuppressed"],
    "lactation": ["breastfeeding", "lactation"],
    "drug_resistant": ["drug-resistant", "multidrug-resistant", "rifampicin-resistant", "mdr-tb", "rr-tb"],
    "inpatient": ["inpatient", "hospitalized"],
    "outpatient": ["outpatient", "ambulatory"],
}

FOLLOWUP_CUES = [
    "what about",
    "how about",
    "and what",
    "and how",
    "what about safety",
    "what about side effects",
    "what about efficacy",
    "what about bedaquiline",
    "what about linezolid",
    "is it safe",
    "and safety",
]


def _extract_heuristic_entities(question: str) -> list[EntityRef]:
    lowered = question.lower()
    entities: list[EntityRef] = []
    if _contains_any(lowered, ["drug-resistant tb", "drug-resistant tuberculosis", "multidrug-resistant", "mdr-tb", "rr-tb", "rifampicin-resistant"]):
        entities.append(EntityRef(name="drug-resistant tuberculosis", kind="condition"))
    elif "tuberculosis" in lowered or " tb " in f" {lowered} ":
        entities.append(EntityRef(name="tuberculosis", kind="condition"))
    if "bedaquiline" in lowered:
        entities.append(EntityRef(name="bedaquiline", kind="drug"))
    if not any(entity.kind == "drug" for entity in entities):
        lowered_compact = lowered.replace("?", "")
        trigger_patterns = ["side effects of ", "safety of ", "safe is ", "about "]
        for trigger in trigger_patterns:
            if trigger in lowered_compact:
                fragment = question[lowered_compact.index(trigger) + len(trigger):].strip(" ?.,")
                candidate = fragment.split()[0].strip(" ?.,")
                if candidate and candidate[0].isalpha() and len(candidate) > 3:
                    entities.append(EntityRef(name=candidate, kind="drug"))
                    break
    if " syndrome" in lowered:
        for token in question.replace("?", "").split(","):
            fragment = token.strip()
            if "syndrome" in fragment.lower():
                entities.append(EntityRef(name=fragment.strip(), kind="condition"))
                break
    return entities


def _extract_clinical_modifiers(question: str) -> list[str]:
    lowered = f" {question.lower()} "
    modifiers: list[str] = []
    for modifier, aliases in MODIFIER_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            modifiers.append(modifier)
    return sorted(set(modifiers))


def _is_followup_like(question: str) -> bool:
    lowered = question.lower().strip()
    return any(lowered.startswith(cue) for cue in FOLLOWUP_CUES)


def _merge_query_with_session_context(parsed: ParsedQuery, session_context: dict) -> ParsedQuery:
    if not session_context or not _is_followup_like(parsed.original_question):
        return parsed

    merged = parsed.model_copy(deep=True)
    active_entities = [EntityRef.model_validate(item) for item in session_context.get("active_entities", [])]
    active_modifiers = list(session_context.get("clinical_modifiers", []))
    active_comorbidities = list(session_context.get("comorbidities", []))
    active_medications = list(session_context.get("medications", []))
    active_population = session_context.get("population")
    active_setting = session_context.get("setting")

    current_condition_entities = [
        entity for entity in merged.entities if entity.kind.lower() in {"condition", "disease", "medical_concept"}
    ]
    inherited_conditions = [
        entity for entity in active_entities if entity.kind.lower() in {"condition", "disease", "medical_concept"}
    ]
    if not current_condition_entities and inherited_conditions:
        merged.entities = inherited_conditions + merged.entities

    if not merged.population and active_population:
        merged.population = active_population
    if not merged.setting and active_setting:
        merged.setting = active_setting
    if not merged.clinical_modifiers and active_modifiers:
        merged.clinical_modifiers = active_modifiers
    else:
        merged.clinical_modifiers = sorted(set(merged.clinical_modifiers + active_modifiers))
    if not merged.comorbidities and active_comorbidities:
        merged.comorbidities = active_comorbidities
    else:
        merged.comorbidities = sorted(set(merged.comorbidities + active_comorbidities))
    if not merged.medications and active_medications:
        merged.medications = active_medications
    else:
        merged.medications = sorted(set(merged.medications + active_medications))
    if "pregnancy" in merged.clinical_modifiers and not merged.pregnancy_status:
        merged.pregnancy_status = "pregnant"

    if merged.rewritten_question == merged.original_question:
        context_bits = [entity.name for entity in inherited_conditions]
        context_bits.extend(modifier.replace("_", " ") for modifier in merged.clinical_modifiers[:3])
        if context_bits:
            merged.rewritten_question = f"{merged.original_question.rstrip('?')} in the context of {', '.join(dict.fromkeys(context_bits))}"
    return merged


def load_session_context(state: dict) -> dict:
    session_context = state.get("session_context", {})
    output = {"session_context": session_context}
    return {
        **output,
        "step_trace": _trace(state, "load_session_context", {}, output),
    }


def parse_query(state: dict) -> dict:
    question = state["user_question"].strip()
    session_context = state.get("session_context", {})
    lowered = question.lower()
    llm_result = llm_service.parse_query(question=question, session_context=session_context)
    if llm_result is not None and not llm_result.clinical_modifiers:
        llm_result.clinical_modifiers = _extract_clinical_modifiers(question)
        if "pregnancy" in llm_result.clinical_modifiers and not llm_result.pregnancy_status:
            llm_result.pregnancy_status = "pregnant"
    if llm_result is not None:
        llm_result = _merge_query_with_session_context(llm_result, session_context)
    if llm_result is not None:
        output = {"parsed_query": llm_result.model_dump(mode="json")}
        return {
            **output,
            "step_trace": _trace(
                state,
                "parse_query",
                {"question": question, "mode": "gemini"},
                output,
            ),
        }

    entities = _extract_heuristic_entities(question)
    clinical_modifiers = _extract_clinical_modifiers(question)
    pregnancy_status = "pregnant" if "pregnancy" in clinical_modifiers else None
    recency_required = _contains_any(lowered, ["latest", "recent", "current"])
    needs_safety = _contains_any(lowered, ["safety", "safe", "side effect", "adverse", "contraindication", "toxicity", "warning"])
    needs_trials = _contains_any(lowered, ["trial", "experimental", "investigational"]) or recency_required
    out_of_scope = _contains_any(lowered, OUT_OF_SCOPE_NEEDLES)

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
        clinical_modifiers=clinical_modifiers,
        comorbidities=[
            modifier
            for modifier in clinical_modifiers
            if modifier
            in {"hiv", "aids", "diabetes", "renal_impairment", "hepatic_impairment", "immunocompromised"}
        ],
        recency_required=recency_required,
        missing_dimensions=missing_dimensions,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        information_needs=information_needs,
        scope_assessment="out_of_scope" if out_of_scope else "in_scope",
        scope_reason=(
            "The question asks about administrative or payer policy rather than medical evidence."
            if out_of_scope
            else None
        ),
    )
    parsed = _merge_query_with_session_context(parsed, session_context)
    output = {"parsed_query": parsed.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "parse_query", {"question": question}, output),
    }


def clarify_or_plan(state: dict) -> dict:
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    tasks: list[SpecialistTask] = []
    if parsed_query.scope_assessment == "out_of_scope":
        response = AssistantResponse(
            status="abstained",
            abstention_class="out_of_scope",
            abstention_reason=parsed_query.scope_reason
            or "This question is outside the configured medical evidence scope.",
            evidence_summary=[],
            limitations=["Current scope is limited to clinical evidence, drug safety, and trial/source retrieval."],
            last_literature_check_at=datetime.now(UTC),
        )
        output = {"final_response": response.model_dump(mode="json"), "pending_tasks": []}
        return {
            **output,
            "step_trace": _trace(state, "clarify_or_plan", {"parsed_query": state["parsed_query"]}, output),
        }
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
    if _contains_any(lowered, ["safety", "safe", "side effect", "adverse", "contraindication", "toxicity", "warning"]):
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
                focus_entities=list(dict.fromkeys([entity.name for entity in parsed_query.entities] + parsed_query.medications)),
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
    if _contains_any(lowered, ["safety", "safe", "side effect", "adverse", "warning", "toxicity"]) and "drug_safety" not in completed_agent_types:
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


def _question_mentions_any(parsed_query: ParsedQuery, needles: list[str]) -> bool:
    return _contains_any(parsed_query.original_question.lower(), needles)


def _has_direct_population_support(parsed_query: ParsedQuery, evidence_items: list[EvidenceItem]) -> bool:
    requested_modifiers = {
        modifier
        for modifier in parsed_query.clinical_modifiers
        if modifier not in {"adult", "outpatient", "inpatient"}
    }
    if not requested_modifiers and not parsed_query.population and not parsed_query.pregnancy_status:
        return True
    for item in evidence_items:
        if item.applicability == "direct":
            return True
        haystack = " ".join([item.population or "", item.key_claim, item.title]).lower()
        modifier_hits = {
            modifier
            for modifier in requested_modifiers
            if any(alias in haystack for alias in MODIFIER_ALIASES.get(modifier, [modifier.replace("_", " ")]))
        }
        if modifier_hits == requested_modifiers:
            return True
        if parsed_query.population and parsed_query.population.lower() in haystack:
            return True
    return False


def _has_condition_support(parsed_query: ParsedQuery, evidence_items: list[EvidenceItem]) -> bool:
    condition_entities = [
        entity.name.lower()
        for entity in parsed_query.entities
        if entity.kind.lower() in {"condition", "disease", "medical_concept"}
    ]
    if not condition_entities:
        return True
    evidence_text = " ".join(
        " ".join(
            [
                item.title,
                item.key_claim,
                item.population or "",
                item.intervention or "",
            ]
        )
        for item in evidence_items
    ).lower()
    matched = 0
    for entity in condition_entities:
        aliases = {entity}
        if "drug-resistant tuberculosis" in entity:
            aliases.update({"tuberculosis", "tb", "rifampicin-resistant tuberculosis", "multidrug-resistant tuberculosis"})
        if any(alias in evidence_text for alias in aliases):
            matched += 1
    return matched > 0


def _has_medication_support(parsed_query: ParsedQuery, evidence_items: list[EvidenceItem]) -> bool:
    requested_medications = {medication.lower() for medication in parsed_query.medications}
    requested_medications.update(
        entity.name.lower()
        for entity in parsed_query.entities
        if entity.kind.lower() in {"drug", "medication"}
    )
    if not requested_medications:
        return False
    evidence_text = " ".join(
        " ".join(
            [
                item.title,
                item.key_claim,
                item.intervention or "",
                " ".join(item.extracted_entities),
            ]
        )
        for item in evidence_items
    ).lower()
    return any(medication in evidence_text for medication in requested_medications)


def _has_safety_support(evidence_items: list[EvidenceItem]) -> bool:
    return any(
        item.claim_type == "safety"
        or bool(item.safety_notes)
        or "safety" in item.supports_question_dimensions
        or item.source_type == "label"
        for item in evidence_items
    )


def _has_recent_evidence(evidence_items: list[EvidenceItem]) -> bool:
    recency_floor = datetime.now(UTC) - timedelta(days=365 * settings.recency_guardrail_years)
    for item in evidence_items:
        if item.publication_date and datetime.combine(item.publication_date, datetime.min.time(), tzinfo=UTC) >= recency_floor:
            return True
    return False


def _evidence_relevance_score(parsed_query: ParsedQuery, item: EvidenceItem) -> tuple[int, int, int]:
    score = item.source_priority * 10
    if item.applicability == "direct":
        score += 25
    elif item.applicability == "indirect":
        score += 10
    if "treatment" in item.supports_question_dimensions:
        score += 12
    if "safety" in item.supports_question_dimensions:
        score += 10
    if "recency" in item.supports_question_dimensions:
        score += 6
    if parsed_query.recency_required and item.publication_date:
        score += 4
    if item.claim_type == "recommendation":
        score += 8
    if item.evidence_strength == "high":
        score += 6
    elif item.evidence_strength == "moderate":
        score += 3
    freshness = item.publication_date.toordinal() if item.publication_date else 0
    return score, freshness, item.source_priority


def _primary_question_dimension(parsed_query: ParsedQuery) -> str:
    lowered = parsed_query.original_question.lower()
    if _contains_any(lowered, ["safety", "safe", "side effect", "adverse", "warning", "contraindication", "toxicity"]):
        return "safety"
    if _contains_any(lowered, ["trial", "trials", "investigational", "experimental", "ongoing study", "registry"]):
        return "trial_status"
    return "treatment"


def _question_role_bonus(primary_dimension: str, item: EvidenceItem) -> int:
    role = item.question_role or item.claim_type or "background"
    bonus_map = {
        "treatment": {
            "treatment": 25,
            "recommendation": 25,
            "safety": 5,
            "trial_status": 4,
            "uncertainty": 8,
            "background": -8,
            "exclude": -30,
        },
        "safety": {
            "safety": 25,
            "treatment": 6,
            "recommendation": 6,
            "trial_status": 2,
            "uncertainty": 8,
            "background": -8,
            "exclude": -30,
        },
        "trial_status": {
            "trial_status": 25,
            "treatment": 6,
            "recommendation": 6,
            "safety": 4,
            "uncertainty": 8,
            "background": -8,
            "exclude": -30,
        },
    }
    return bonus_map.get(primary_dimension, {}).get(role, 0)


def _apply_llm_evidence_assessment(
    parsed_query: ParsedQuery,
    evidence_items: list[EvidenceItem],
) -> list[EvidenceItem]:
    assessment = llm_service.assess_evidence(parsed_query=parsed_query, evidence_items=evidence_items)
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
                    "semantic_relevance": assessed.semantic_relevance,
                }
            )
        )
    return updated


def _order_evidence_items(parsed_query: ParsedQuery, evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    primary_dimension = _primary_question_dimension(parsed_query)
    deterministically_ordered = sorted(
        evidence_items,
        key=lambda item: _evidence_relevance_score(parsed_query, item),
        reverse=True,
    )
    assessed_items = _apply_llm_evidence_assessment(parsed_query, deterministically_ordered[:8])
    if len(deterministically_ordered) > 8:
        assessed_items.extend(deterministically_ordered[8:])
    return sorted(
        assessed_items,
        key=lambda item: (
            (item.semantic_relevance or 0) + _question_role_bonus(primary_dimension, item),
            *_evidence_relevance_score(parsed_query, item),
        ),
        reverse=True,
    )


def _select_synthesis_evidence(parsed_query: ParsedQuery, evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    primary_dimension = _primary_question_dimension(parsed_query)
    allowed_by_dimension = {
        "treatment": {"treatment", "recommendation", "safety", "uncertainty", "background"},
        "safety": {"safety", "treatment", "recommendation", "uncertainty", "background"},
        "trial_status": {"trial_status", "treatment", "recommendation", "uncertainty", "background"},
    }
    allowed_roles = allowed_by_dimension.get(primary_dimension, {"treatment", "recommendation", "background"})
    filtered = [
        item
        for item in evidence_items
        if (item.question_role or item.claim_type or "background") in allowed_roles
        and (item.question_role or "") != "exclude"
    ]
    if not filtered:
        filtered = [item for item in evidence_items if (item.question_role or "") != "exclude"]
    return filtered[:6]


def _soft_verification_limitations(unsupported_claims: list[str]) -> list[str]:
    mapping = {
        "population_mismatch": "The retrieved evidence does not directly match the requested patient population, so the answer is based partly on indirect evidence.",
        "weak_evidence_base": "The available evidence base is limited and should be interpreted cautiously.",
    }
    return [mapping[claim] for claim in unsupported_claims if claim in mapping]


def _apply_verification_guardrails(
    parsed_query: ParsedQuery,
    draft: AssistantResponse,
    verification: VerificationResult,
    evidence_items: list[EvidenceItem],
) -> VerificationResult:
    if draft.status != "answered":
        return verification

    unsupported = list(verification.unsupported_claims)
    abstention_class = verification.abstention_class
    abstention_reason = verification.abstention_reason
    safety_question = _question_mentions_any(parsed_query, ["safety", "safe", "side effect", "adverse", "warning", "contraindication"])

    if not draft.citations:
        unsupported.append("draft_answer_missing_citations")
        abstention_class = abstention_class or "insufficient_evidence"
        abstention_reason = abstention_reason or "The answer draft does not contain supporting citations."

    if parsed_query.recency_required and not _has_recent_evidence(evidence_items):
        unsupported.append("no_recent_evidence")
        abstention_class = "recency_gap"
        abstention_reason = "The available evidence does not include sufficiently recent sources for a recency-sensitive question."

    if not _has_direct_population_support(parsed_query, evidence_items):
        unsupported.append("population_mismatch")
        abstention_class = abstention_class or "coverage_gap"
        abstention_reason = abstention_reason or "The retrieved evidence does not directly address the requested patient population."

    if not _has_condition_support(parsed_query, evidence_items) and not (
        safety_question and _has_safety_support(evidence_items) and _has_medication_support(parsed_query, evidence_items)
    ):
        unsupported.append("condition_mismatch")
        abstention_class = abstention_class or "coverage_gap"
        abstention_reason = abstention_reason or "The retrieved evidence does not directly address the requested clinical condition."

    if safety_question and not _has_safety_support(evidence_items):
        unsupported.append("missing_direct_safety_support")
        abstention_class = abstention_class or "coverage_gap"
        abstention_reason = abstention_reason or "The retrieved sources do not provide direct safety support for the requested question."
    if safety_question and (
        parsed_query.medications
        or any(entity.kind.lower() in {"drug", "medication"} for entity in parsed_query.entities)
    ) and not _has_medication_support(parsed_query, evidence_items):
        unsupported.append("medication_mismatch")
        abstention_class = abstention_class or "coverage_gap"
        abstention_reason = abstention_reason or "The retrieved evidence does not directly address the requested medication."

    if all(item.evidence_strength == "low" for item in evidence_items) and len(evidence_items) < 2:
        unsupported.append("weak_evidence_base")
        abstention_class = abstention_class or "insufficient_evidence"
        abstention_reason = abstention_reason or "The answer is based on a very limited low-strength evidence set."

    hard_blockers = {
        "draft_answer_missing_citations",
        "no_recent_evidence",
        "condition_mismatch",
        "missing_direct_safety_support",
        "medication_mismatch",
    }
    soft_blockers = {
        "population_mismatch",
        "weak_evidence_base",
    }
    unsupported_set = set(unsupported)
    has_hard_blockers = bool(unsupported_set & hard_blockers)
    only_soft_blockers = unsupported_set and unsupported_set.issubset(soft_blockers)
    verifier_forces_abstention = verification.status == "abstain" and (
        bool(verification.conflicts)
        or verification.abstention_class in {"conflicting_evidence", "missing_clinical_context", "ambiguous_query", "recency_gap"}
    )

    if verification.status == "abstain" and unsupported and not abstention_class:
        abstention_class = "insufficient_evidence"
    if verification.status == "abstain" and unsupported and not abstention_reason:
        abstention_reason = "The drafted answer included claims that could not be fully supported by the retrieved evidence."

    final_status = "pass"
    if has_hard_blockers or verifier_forces_abstention:
        final_status = "abstain"
    elif verification.status == "clarify":
        final_status = "clarify"
    elif verification.status == "abstain" and not only_soft_blockers:
        final_status = "abstain"

    return VerificationResult(
        status=final_status,
        supported_claims=verification.supported_claims,
        unsupported_claims=sorted(set(unsupported)),
        conflicts=verification.conflicts,
        abstention_class=abstention_class if final_status == "abstain" else None,
        abstention_reason=abstention_reason if final_status == "abstain" else None,
    )


def synthesize_answer(state: dict) -> dict:
    evidence_items = [EvidenceItem.model_validate(item) for item in state.get("evidence_items", [])]
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    evidence_items = _order_evidence_items(parsed_query, evidence_items)
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
    top_evidence = _select_synthesis_evidence(parsed_query, evidence_items)
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
        evidence_summary.append(item.key_claim)
        if item.safety_notes:
            safety_notes.extend(item.safety_notes)

    llm_draft = llm_service.synthesize_answer(
        parsed_query=parsed_query,
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
        output = {"draft_response": response.model_dump(mode="json")}
        return {
            **output,
            "step_trace": _trace(
                state,
                "synthesize_answer",
                {"evidence_count": len(evidence_items), "mode": "gemini"},
                {"citation_count": len(citations)},
            ),
        }

    lead_item = top_evidence[0]
    answer_lines.append(lead_item.key_claim)
    if parsed_query.clinical_modifiers:
        answer_lines.append(
            "The available evidence should still be interpreted in light of the requested clinical modifiers, because directly matching evidence may remain limited."
        )
    if safety_notes:
        answer_lines.append(f"Key safety considerations mentioned in retrieved evidence include {', '.join(sorted(set(safety_notes)))}.")

    response = AssistantResponse(
        status="answered",
        answer=" ".join(answer_lines),
        evidence_summary=evidence_summary,
        evidence_strength=(
            "high"
            if any(item.evidence_strength == "high" for item in evidence_items)
            else "moderate"
            if any(item.evidence_strength == "moderate" for item in evidence_items)
            else "low"
        ),
        limitations=[
            "This deployable MVP currently mixes mock retrieval with real orchestration and should not be treated as production clinical decision support."
        ],
        citations=citations,
        evidence_items=top_evidence,
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
    parsed_query = ParsedQuery.model_validate(state["parsed_query"])
    evidence_items = [EvidenceItem.model_validate(item) for item in state.get("evidence_items", [])]
    llm_verification = llm_service.verify_answer(
        parsed_query=parsed_query,
        draft_response=draft,
        evidence_items=evidence_items[:6],
    )
    if llm_verification is not None:
        guarded = _apply_verification_guardrails(parsed_query, draft, llm_verification, evidence_items)
        output = {"verification_result": guarded.model_dump(mode="json")}
        return {
            **output,
            "step_trace": _trace(
                state,
                "verify_answer",
                {"draft_status": draft.status, "mode": "gemini"},
                output,
            ),
        }

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
                claim_text=item.key_claim,
                supporting_source_ids=[item.source_id],
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

    verification = _apply_verification_guardrails(parsed_query, draft, verification, evidence_items)

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
            merged_limitations = list(dict.fromkeys(draft.limitations + _soft_verification_limitations(verification.unsupported_claims)))
            final = draft.model_copy(update={"limitations": merged_limitations})
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
                evidence_items=draft.evidence_items,
                last_literature_check_at=datetime.now(UTC),
            )

    output = {"final_response": final.model_dump(mode="json")}
    return {
        **output,
        "step_trace": _trace(state, "finalize_response", {}, output),
    }
