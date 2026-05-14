# Chiron Implementation Decisions Q&A

## Purpose

This document collects the remaining decisions that matter for implementation.

Format:

- `Question`: the decision to be made
- `Recommended Answer`: the current recommendation
- `Why`: short rationale

This is intended to be reviewed and edited. Once revised, it should become the locked decision reference for implementation.

## How To Use This Document

- If you agree with a recommendation, leave it as-is.
- If you disagree, edit the answer directly.
- If a recommendation is too loose, replace it with a tighter final answer.
- After review, this document should be treated as the implementation source of truth for unresolved choices that are not already fully locked elsewhere.

---

## 1. Product and Scope Decisions

### Q1. What is the core product contract?

**Recommended Answer**  
The product accepts open-domain medical questions and must return exactly one of three outcomes:

- a grounded answer with citations and dates
- a clarification request
- a structured abstention

**Why**  
This keeps the input space open while tightly constraining output behavior.

### Q2. Is this system global or India-specific?

**Recommended Answer**  
The MVP should be `global evidence-based medicine first`, with geography-specific weighting deferred to a later extension.

**Why**  
This avoids locking the system to India-specific guideline and regulatory behavior too early while still leaving room for future regional weighting.

### Q3. Should the MVP include Ayurveda, homeopathy, or other alternative medicine systems?

**Recommended Answer**  
No. The MVP should cover evidence-based medicine only. Alternative medicine is out of scope unless explicitly requested in a future version and clearly separated.

**Why**  
Including alternative systems weakens the trust and evaluation story for the assignment.

### Q4. Is this a patient-specific decision support system?

**Recommended Answer**  
No. The MVP may accept patient context as constraints in a question, but it remains an evidence assistant, not a personalized clinical decision engine.

**Why**  
This keeps the system useful without crossing into more complex clinical support obligations.

### Q5. Does the MVP need multi-turn interaction?

**Recommended Answer**  
Yes, but only `session-scoped` multi-turn interaction. The MVP should support clarification and follow-up within a chat session, but not persistent longitudinal memory across sessions.

**Why**  
Clarification is essential. Long-term cross-session memory is not.

### Q6. What is the frontend/backend product split?

**Recommended Answer**  
The frontend owns session UX, conversation history rendering, input, and evidence presentation. The backend owns orchestration, retrieval, normalization, verification, and final response state.

**Why**  
This cleanly separates presentation from evidence logic.

---

## 2. Repository and Application Structure Decisions

### Q7. Should the repo be split into `frontend/` and `backend/`?

**Recommended Answer**  
Yes. Use a monorepo with separate `frontend/` and `backend/` folders.

**Why**  
The frontend is delegated separately, and backend complexity warrants clean isolation.

### Q8. What top-level repo folders should exist?

**Recommended Answer**  
Use:

- `frontend/`
- `backend/`
- `docs/`
- `PRDs/`
- `eval/`

**Why**  
This is enough structure without overengineering the repo.

### Q9. Should the backend be a modular monolith or microservices for the MVP?

**Recommended Answer**  
Use a `modular monolith`.

**Why**  
Correctness, provenance, and evaluation are more important than distributed scale in the MVP.

### Q10. Should the architecture be designed for later scale-out?

**Recommended Answer**  
Yes. Keep clean seams so retrieval workers, evaluation runners, or queues can be extracted later, but do not implement distributed infrastructure upfront.

**Why**  
This shows architectural foresight without premature complexity.

---

## 3. Backend Stack Decisions

### Q11. What backend language should be used?

**Recommended Answer**  
Python 3.12.

**Why**  
Best ecosystem fit for LLM orchestration, medical source integration, and rapid backend iteration.

### Q12. What web framework should be used?

**Recommended Answer**  
FastAPI.

**Why**  
It pairs well with typed schemas, async I/O, and frontend-friendly APIs.

### Q13. What schema library should be used?

**Recommended Answer**  
Pydantic v2.

**Why**  
It works well for request/response contracts, model output validation, and internal typed data flow.

### Q14. What ORM and migration tools should be used?

**Recommended Answer**  
SQLAlchemy 2.x with Alembic.

**Why**  
Mature, explicit, and suitable for a backend with persistent run and evidence data.

### Q15. What database should be used?

**Recommended Answer**  
PostgreSQL.

**Why**  
Good default relational store for sessions, runs, citations, and evaluations.

### Q16. Should Redis be required from day one?

**Recommended Answer**  
Redis should be included in the architecture, but real runtime dependence can be deferred until after the first working vertical slice unless caching is needed immediately.

**Why**  
It avoids slowing down the first end-to-end path while preserving a useful cache/worker coordination layer.

### Q17. What HTTP client should source connectors use?

**Recommended Answer**  
`httpx`.

**Why**  
Clean async support and strong Python ergonomics.

### Q18. Which LLM provider should be the primary backend target?

**Recommended Answer**  
Gemini via the Google GenAI Python SDK.

**Why**  
The account is already set up, the SDK is familiar, and structured outputs are good enough for this architecture.

### Q19. Should the codebase be provider-agnostic from day one?

**Recommended Answer**  
Not fully. It should be provider-aware with a thin abstraction around LLM calls, but not overdesigned into a full multi-provider platform.

**Why**  
This avoids premature abstraction while leaving a migration path.

### Q20. What dependency manager should be used?

**Recommended Answer**  
`uv`.

**Why**  
Fast, modern, and a good fit for a Python-first backend with a fresh codebase.

---

## 4. Orchestration and Agent Runtime Decisions

### Q21. Should backend orchestration use plain `asyncio` or LangGraph?

**Recommended Answer**  
Use LangGraph as the orchestration runtime.

**Why**  
The workflow is stateful, branching, iterative, and interruptible. A graph runtime fits better than a hand-rolled loop.

### Q22. What role should LangGraph play?

**Recommended Answer**  
LangGraph should own orchestration control flow, shared run state, checkpointing, and node transitions.

**Why**  
That is its natural role in this system.

### Q23. What should LangGraph not be used for?

**Recommended Answer**  
Do not use LangGraph as a replacement for:

- persistence models
- source connectors
- generic utilities
- business validation modules
- frontend state

**Why**  
Overusing it will make the codebase harder to reason about.

### Q24. Should there be one general agent or multiple specialists?

**Recommended Answer**  
Use one top-level orchestrator plus multiple specialist agents.

**Why**  
This preserves open-domain input while improving internal capability control.

### Q25. How should specialist agents be defined?

**Recommended Answer**  
Define them by `evidence source/type`, not by superficial user query labels.

Use:

- query parser
- guideline agent
- literature agent
- drug-safety agent
- trials agent
- synthesizer
- verifier

**Why**  
Real medical questions often span multiple evidence types.

### Q26. Should users be routed into rigid intent buckets?

**Recommended Answer**  
No. The user-facing contract remains open-domain. Internal decomposition should decide which specialists to invoke.

**Why**  
Rigid buckets would weaken the core product premise.

### Q27. Should specialists share the same toolbox?

**Recommended Answer**  
No. Each specialist should receive only the connectors and capabilities relevant to its role.

**Why**  
This improves control, traceability, and failure isolation.

### Q28. Does that require OS-level sandboxing?

**Recommended Answer**  
No. Use logical capability gating, not process/container sandboxing, for the MVP.

**Why**  
The assignment does not justify the infrastructure cost of hard sandboxing.

### Q29. Should the orchestrator support both parallel and sequential execution?

**Recommended Answer**  
Yes.

**Why**  
Some evidence needs are independent and should fan out in parallel, while others depend on earlier outputs and must run sequentially.

### Q30. Should the orchestrator support multiple passes?

**Recommended Answer**  
Yes. The orchestrator should support iterative deepening with bounded follow-up tasks.

**Why**  
Many medical questions require second-pass retrieval after initial evidence surfaces candidate drugs, trials, or gaps.

### Q31. What should the initial graph nodes be?

**Recommended Answer**  
Use:

- `load_session_context`
- `parse_query`
- `clarify_or_plan`
- `dispatch_specialists`
- `aggregate_evidence`
- `assess_gaps`
- `replan_or_continue`
- `synthesize_answer`
- `verify_answer`
- `finalize_response`

**Why**  
This keeps the graph explicit but still understandable.

### Q32. What hard loop limits should the MVP enforce?

**Recommended Answer**  
Use:

- max orchestration iterations: `3`
- max specialist tasks per run: `8`
- max structured-output retries per node: `2`

**Why**  
These are safe initial bounds against runaway loops.

### Q33. How should clarification interrupts work?

**Recommended Answer**  
When clarification is required, the graph should stop at a stable checkpoint and return `needs_clarification`. The next user turn creates a new run using enriched session context.

**Why**  
This is simpler and safer than arbitrary mid-graph resumption.

### Q34. What checkpoint backend should be used first?

**Recommended Answer**  
Use in-memory or lightweight local checkpointing initially. Move to persistent checkpoint storage after the graph shape is stable.

**Why**  
It reduces early complexity while preserving the architectural path.

---

## 5. Source and Retrieval Decisions

### Q35. What sources are mandatory in the MVP?

**Recommended Answer**  
The MVP source set must include:

- PubMed
- Europe PMC
- PubMed Central open-access content where available
- ClinicalTrials.gov
- DailyMed
- a public guideline layer

**Why**  
This covers literature, open full text, trials, drug-label data, and guideline authority.

### Q36. Which guideline sources should be allowlisted first?

**Recommended Answer**  
Start with:

- WHO
- NICE
- CDC
- NIH

**Why**  
These are public, high-trust, and broadly useful.

### Q37. Should unrestricted web search be part of the MVP?

**Recommended Answer**  
No.

**Why**  
The trust story is stronger if the source surface is explicitly allowlisted.

### Q38. Should `openFDA` be in the MVP?

**Recommended Answer**  
Treat `openFDA` as an optional stretch source.

**Why**  
DailyMed already gives a strong drug-safety base, and `openFDA` is more useful as an additional signal than a foundation.

### Q39. Should `Drugs@FDA` be in the MVP?

**Recommended Answer**  
Optional. Add it only if the benchmark shows a meaningful gap that DailyMed does not cover well enough.

**Why**  
Avoid source sprawl unless it materially improves answers.

### Q40. How should evidence be ranked?

**Recommended Answer**  
Rank by:

1. source authority
2. evidence type
3. recency
4. applicability to the question

Do not rank primarily by journal brand.

**Why**  
A current guideline often outranks a newer single paper in a prestigious journal.

### Q41. Should preprints be included?

**Recommended Answer**  
No for the MVP, unless explicitly flagged and isolated.

**Why**  
They complicate trust and evaluation.

### Q42. Should connectors return raw source-specific payloads to the orchestrator?

**Recommended Answer**  
No. Connectors should normalize into a shared `SourceDocument` contract.

**Why**  
This prevents the orchestrator from being polluted by source-specific shapes.

---

## 6. Session, State, and Persistence Decisions

### Q43. What is the difference between session state and graph state?

**Recommended Answer**  
Session state is the long-lived conversation context stored by the application. Graph state is the per-run orchestration state used by LangGraph.

**Why**  
These are different lifecycles and should not be conflated.

### Q44. What should be stored in session state?

**Recommended Answer**  
Store:

- session ID
- message history
- compact structured context derived from the conversation
- current unresolved clarification dimensions if applicable

**Why**  
The session should provide enough context without forcing every run to ingest the entire raw transcript.

### Q45. What should be stored in graph state?

**Recommended Answer**  
Store:

- current user message
- compact session context snapshot
- parsed query
- pending specialist tasks
- completed task results
- normalized evidence items
- unresolved gaps
- draft answer
- verification result
- final response

**Why**  
This is the state the workflow needs to compute the run.

### Q46. Should raw full conversation history be injected into every model call?

**Recommended Answer**  
No.

**Why**  
That increases noise, cost, and instability. Use a compact session context plus relevant recent turns.

### Q47. What session-compaction strategy should be used?

**Recommended Answer**  
Use:

- a small recent-turn window
- a structured session summary/context object

Do not rely on full raw transcript stuffing.

**Why**  
This is a better balance of context quality and prompt discipline.

### Q48. What core relational tables should exist initially?

**Recommended Answer**  
Start with:

- `chat_sessions`
- `chat_messages`
- `runs`
- `run_steps`
- `sources`
- `evidence_items`
- `answer_claims`
- `claim_citations`
- `eval_questions`
- `eval_runs`
- `eval_results`

**Why**  
This covers conversation state, orchestration traceability, evidence provenance, and evaluation.

### Q49. Should LangGraph checkpoint state replace Postgres persistence?

**Recommended Answer**  
No.

**Why**  
Checkpointing is for orchestration flow. Postgres remains the source of truth for product data and trace records.

---

## 7. Schema Decisions

### Q50. Should all internal contracts be typed and validated?

**Recommended Answer**  
Yes. All model-facing and connector-facing contracts should use explicit Pydantic models.

**Why**  
This reduces ambiguity and prevents malformed outputs from propagating.

### Q51. What assistant response statuses should be supported?

**Recommended Answer**  
Use exactly:

- `answered`
- `needs_clarification`
- `abstained`

**Why**  
These are the three product-level outcomes.

### Q52. What evidence-strength enum should be used in the MVP?

**Recommended Answer**  
Use:

- `high`
- `moderate`
- `low`
- `unknown`

**Why**  
Simple and sufficient for MVP communication and ranking.

### Q53. What abstention classes should be supported?

**Recommended Answer**  
Use:

- `insufficient_evidence`
- `conflicting_evidence`
- `missing_clinical_context`
- `coverage_gap`
- `recency_gap`
- `ambiguous_query`

**Why**  
These map cleanly to the refusal taxonomy already defined.

### Q54. What specialist agent type enum should be used?

**Recommended Answer**  
Use:

- `guideline`
- `literature`
- `drug_safety`
- `trials`

**Why**  
These are the source-type specialists for the MVP.

### Q55. What fields should `ParsedQuery` contain?

**Recommended Answer**  
`ParsedQuery` should contain:

- `original_question`
- `rewritten_question`
- `entities`
- `population`
- `setting`
- `pregnancy_status`
- `comorbidities`
- `medications`
- `recency_required`
- `missing_dimensions`
- `needs_clarification`
- `clarification_question`
- `information_needs`

**Why**  
This is enough for planning and clarification without overfitting the schema.

### Q56. What fields should `SpecialistTask` contain?

**Recommended Answer**  
`SpecialistTask` should contain:

- `task_id`
- `agent_type`
- `goal`
- `subquery`
- `depends_on`
- `focus_entities`

**Why**  
This is enough to support graph scheduling and task dependency handling.

### Q57. What fields should `SourceDocument` contain?

**Recommended Answer**  
`SourceDocument` should contain:

- `source_id`
- `source_type`
- `title`
- `url`
- `publication_date`
- `publisher`
- `abstract`
- `full_text`
- `metadata`

**Why**  
This is a stable normalized source shape.

### Q58. What fields should `EvidenceItem` contain?

**Recommended Answer**  
`EvidenceItem` should contain:

- `evidence_id`
- `source_id`
- `source_type`
- `title`
- `url`
- `publication_date`
- `population`
- `intervention`
- `outcome`
- `key_claim`
- `safety_notes`
- `limitations`
- `evidence_strength`
- `extracted_entities`

**Why**  
This is compact but expressive enough for synthesis and verification.

### Q59. What fields should `AssistantResponse` contain?

**Recommended Answer**  
`AssistantResponse` should contain:

- `status`
- `answer`
- `clarification_question`
- `abstention_class`
- `abstention_reason`
- `evidence_summary`
- `evidence_strength`
- `limitations`
- `citations`
- `last_literature_check_at`

**Why**  
This captures all three product outcomes in a single stable contract.

### Q60. What fields should `VerificationResult` contain?

**Recommended Answer**  
`VerificationResult` should contain:

- `status`
- `supported_claims`
- `unsupported_claims`
- `conflicts`
- `abstention_class`
- `abstention_reason`

**Why**  
This is enough for the verifier to act as a final gate.

### Q61. Should schemas be large and deeply nested?

**Recommended Answer**  
No. Keep schemas narrow and task-specific.

**Why**  
Structured output reliability drops when schemas become too ambitious.

### Q62. Should one LLM call do parsing, extraction, synthesis, and verification at once?

**Recommended Answer**  
No.

**Why**  
Each stage should have its own schema and validation boundary.

---

## 8. API and Interaction Decisions

### Q63. Does the backend need a stable response contract before the frontend is complete?

**Recommended Answer**  
Yes.

**Why**  
The frontend can scaffold against state shapes even if exact routes evolve later.

### Q64. What interaction surfaces should the backend support?

**Recommended Answer**  
Support:

- session creation and retrieval
- message submission
- run inspection
- evaluation execution and reporting

**Why**  
These are the minimum backend surfaces needed for product flow and debugging.

### Q65. Should streaming be required in the MVP?

**Recommended Answer**  
No. It is optional.

**Why**  
Correctness and traceability matter more than streaming polish in the MVP.

### Q66. Should the frontend treat the backend as the source of truth for answer state?

**Recommended Answer**  
Yes.

**Why**  
The backend owns answerability, clarification, abstention, and evidence decisions.

---

## 9. LLM and Structured Output Decisions

### Q67. Should Gemini structured outputs be used throughout the backend?

**Recommended Answer**  
Use structured outputs at the critical typed boundaries:

- query parsing
- specialist task planning
- evidence extraction
- synthesis metadata
- verification

**Why**  
These are the points where typed contracts materially improve reliability.

### Q68. Should LLM outputs be trusted without validation?

**Recommended Answer**  
No.

**Why**  
Every model output must be schema-validated and, where needed, semantically checked.

### Q69. What should happen when a structured output is invalid?

**Recommended Answer**  
Retry up to two times. If still invalid, treat it as a node-level failure and surface a safe fallback or failure state.

**Why**  
Malformed outputs should not silently leak downstream.

### Q70. Should the synthesizer have direct source connector access?

**Recommended Answer**  
No. The synthesizer should consume normalized evidence only.

**Why**  
This enforces grounding and keeps retrieval separate from answer drafting.

### Q71. Should the verifier have direct source connector access?

**Recommended Answer**  
No. The verifier should inspect parsed query, evidence, and draft answer only.

**Why**  
It is a gating role, not a retrieval role.

---

## 10. Testing and Evaluation Decisions

### Q72. Is the evaluation harness part of the MVP or post-MVP?

**Recommended Answer**  
It is part of the MVP.

**Why**  
The assignment is about demonstrating trustworthiness, not just building a demo.

### Q73. What benchmark strata should be included?

**Recommended Answer**  
Include:

- direct lookup
- multi-source synthesis
- drug safety
- differential-style knowledge prompts
- latest-evidence prompts
- should-refuse prompts
- adversarial fake-entity prompts
- ambiguous prompts requiring clarification
- clarification-to-answer multi-turn flows

**Why**  
This covers the major success and failure cases.

### Q74. How large should the benchmark be initially?

**Recommended Answer**  
Target `40 to 60` questions.

**Why**  
Large enough to be credible, small enough to manage in an assignment setting.

### Q75. What should connector testing use?

**Recommended Answer**  
Use a hybrid of:

- recorded fixtures for realistic source payloads
- hand-built mocks for edge cases and failure conditions

**Why**  
This gives realism without overdependence on live APIs.

### Q76. What are the core acceptance criteria for MVP trustworthiness?

**Recommended Answer**  
Require:

- no fabricated citations in the benchmark set
- no materially unsupported answer claims
- strong abstention correctness on unsafe or unanswerable prompts
- explicit date awareness for recency-sensitive queries
- visible preference for stronger evidence where available

**Why**  
These criteria match the product’s core promise.

---

## 11. Operational and Observability Decisions

### Q77. What should every run log or persist for observability?

**Recommended Answer**  
Persist:

- input message
- session context snapshot
- parsed query
- planned tasks
- task timings
- retrieved sources
- normalized evidence
- synthesis output
- verification output
- final response

**Why**  
This is needed for debugging, evaluation, and demo transparency.

### Q78. What graph-level metadata should be recorded?

**Recommended Answer**  
Record:

- `graph_node`
- `graph_iteration`
- `checkpoint_id`
- `task_id`
- `dependency_task_ids`
- `latency_ms`
- `status`

**Why**  
These fields make orchestration behavior inspectable.

### Q79. Should a queue system be required for the MVP?

**Recommended Answer**  
No.

**Why**  
The modular monolith should be enough initially.

### Q80. When should worker extraction or a queue be introduced later?

**Recommended Answer**  
Only if one of these becomes true:

- specialist retrieval causes sustained latency bottlenecks
- source connector load needs separate horizontal scaling
- evaluation workloads become operationally heavy
- deployment cadence requires separation

**Why**  
This keeps infrastructure tied to real bottlenecks.

---

## 12. Frontend Coordination Decisions

### Q81. How tightly should backend implementation depend on the frontend?

**Recommended Answer**  
Minimally. The backend should expose stable response states and evidence metadata, but not depend on frontend routing or component structure.

**Why**  
Frontend work is delegated and should not block backend design.

### Q82. What UI states must the backend be able to drive?

**Recommended Answer**  
The backend must be able to drive:

- idle or initial ready state via frontend defaults
- loading via frontend request state
- answered
- clarification needed
- abstained
- error

**Why**  
These are the key UX states the frontend brief already assumes.

---

## 13. Deferred Decisions

### Q83. What should be explicitly deferred until after MVP?

**Recommended Answer**  
Defer:

- microservices
- distributed queues
- per-agent containers
- unrestricted web search
- provider-agnostic multi-LLM routing
- persistent cross-session case memory
- advanced formal evidence-grading frameworks

**Why**  
These are not required to prove the MVP thesis.

### Q84. What should be the near-term post-MVP scale-up path if extra time remains?

**Recommended Answer**  
Prioritize:

1. connector caching hardening
2. richer guideline coverage
3. worker extraction for long-running specialist calls
4. improved evaluation reporting
5. stronger persistent graph checkpoints

**Why**  
These improve capability and reliability without destabilizing the architecture.

---

## 14. Decisions That Still Need Explicit Final Confirmation

These are the few items most worth actively confirming before backend coding starts:

### Q85. What dependency manager is final?

**Recommended Answer**  
`uv`

### Q86. Should Redis be required in the first vertical slice or deferred?

**Recommended Answer**  
Deferred unless caching pain appears immediately.

### Q87. Are `WHO`, `NICE`, `CDC`, and `NIH` the final initial guideline allowlist?

**Recommended Answer**  
Yes.

### Q88. Is `openFDA` officially stretch-only for MVP?

**Recommended Answer**  
Yes.

### Q89. Is the evidence-strength enum final as `high|moderate|low|unknown`?

**Recommended Answer**  
Yes.

### Q90. Is the initial LangGraph checkpoint strategy `in-memory first, persistent later`?

**Recommended Answer**  
Yes.

---

## 15. Summary Recommendation

If nothing else is changed, the implementation should proceed with these defaults:

- modular monolith
- `frontend/` and `backend/` split
- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x + Alembic
- PostgreSQL
- Redis available but not mandatory in the first slice
- Gemini as the primary model provider
- LangGraph as the orchestration runtime
- capability-gated source-type specialists
- session-scoped chat memory only
- allowlisted medical evidence sources only
- typed schemas at every critical boundary
- evaluation harness included in MVP

Once reviewed and edited, this document should be treated as the final implementation decision sheet.
