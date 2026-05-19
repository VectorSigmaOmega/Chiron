# Chiron Architecture

## 1. Purpose

`Chiron` is an open-domain medical evidence assistant for clinicians. A user may ask any medical question. The system must either:

- answer from retrieved evidence with citations and dates
- ask for clarification when the query is underspecified
- abstain when the evidence is insufficient, conflicting, outdated, or outside supported scope

This document defines the architecture for the MVP and the path to scale it later.

## 2. Architectural Principles

- Open-ended input, bounded output
- Evidence retrieval before synthesis
- Capability-gated specialist agents, not one unrestricted model
- Session-scoped conversation context, not persistent cross-session memory
- Modular monolith for the MVP, with clean seams for later extraction
- Structured outputs validated in code at every LLM boundary
- Full provenance and traceability for every run

## 3. Technology Stack

### Backend

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis for cache and optional future task queue coordination
- `httpx` for external API calls
- Gemini API via the Google GenAI Python SDK
- LangGraph for orchestration and run-state management

### Frontend

- Separate application in `frontend/`
- Chat-based UI with evidence panel
- Session history stored at the application layer

### Orchestration

- LangGraph `StateGraph` as the orchestration runtime
- custom node logic inside the backend
- Parallel fan-out for independent specialist tasks
- Sequential follow-up tasks when prior evidence introduces new entities or gaps
- checkpointed run state for pause/resume and traceability

### Testing and Evaluation

- `pytest`
- contract tests for connectors
- integration tests for orchestration flows
- evaluation harness driven by benchmark questions

## 4. Repository Shape

The repository should be organized as a monorepo with separate frontend and backend applications.

```text
frontend/
backend/
docs/
PRDs/
eval/
```

Recommended backend shape:

```text
backend/
  app/
    api/
    core/
    orchestration/
      graph/
      nodes/
      policies/
    agents/
    connectors/
    schemas/
    persistence/
    services/
    evaluation/
  tests/
```

## 5. Deployment Model

The MVP should be deployed as a modular monolith:

- one backend service
- one frontend service
- one PostgreSQL instance
- one Redis instance

This keeps correctness, traceability, and debugging simple while preserving the option to extract workers later.

The MVP should become deployable before broad connector coverage is complete. A working backend scaffold with mock connectors and a compiled orchestration graph is a valid milestone, not an incomplete side task.

## 6. High-Level Runtime Architecture

```text
Frontend Chat UI
    |
    v
FastAPI API Layer
    |
    v
Session + Run Service
    |
    v
Orchestrator
    |-----------------------------|
    |             |               |
    v             v               v
Guideline     Literature      Drug Safety
Agent         Agent           Agent
    |             |               |
    v             v               v
ECRI Search    PubMed / PMC    DailyMed /
-> original    literature      Drugs@FDA / openFDA
document
    |
    |-----------------------------|
                  |
                  v
             Trials Agent
                  |
                  v
          ClinicalTrials.gov

All specialist outputs
        |
        v
Evidence Normalizer
        |
        v
Synthesizer
        |
        v
Verifier / Refusal Gate
        |
        v
Assistant Response + Citations
```

## 7. Core Components

### 7.1 Frontend

Responsibilities:

- render chat history for a session
- send a user message to the backend
- display one of three backend states: answered, clarification needed, abstained
- show evidence citations, source dates, and limitations

The frontend must not implement evidence logic. It is a client of the backend response contract.

### 7.2 API Layer

Responsibilities:

- expose session and message endpoints
- validate requests and responses
- create and track orchestration runs
- serve evaluation endpoints for benchmark execution

### 7.3 Session Service

Responsibilities:

- create chat sessions
- store user and assistant messages
- build a compact session context object for the orchestrator
- separate conversation history from agent execution state

### 7.4 Orchestrator

The orchestrator is a LangGraph-backed stateful evidence planner. It is not a simple classifier or router.

Responsibilities:

- parse each user turn
- determine whether clarification is required
- plan initial specialist subtasks
- run parallel tasks when independent
- trigger sequential follow-up tasks when prior evidence introduces new entities or unresolved gaps
- stop when there is enough evidence to answer or a refusal threshold is reached
- checkpoint graph state between major steps
- support interruption at clarification boundaries

### 7.5 Specialist Agents

Specialists are internal execution modules with restricted toolboxes.

The user question is not forced into one bucket. The orchestrator decides which specialists are needed and may invoke several of them for one question.

### 7.6 Evidence Normalizer

Responsibilities:

- convert specialist outputs into a shared evidence schema
- deduplicate equivalent source records
- preserve provenance and source metadata
- prepare normalized evidence for synthesis and verification

### 7.7 Synthesizer

Responsibilities:

- draft a grounded answer from normalized evidence only
- summarize uncertainty and limitations
- produce structured claims with citation references

The synthesizer must not access raw browsing or unrestricted connectors.

### 7.8 Verifier / Refusal Gate

Responsibilities:

- confirm each substantive claim is supported by evidence items
- identify missing support, conflicts, and recency issues
- downgrade to clarification or abstention when necessary
- enforce the final response contract

## 8. Specialist Agent Topology

### 8.1 Query Parser

Role:

- turn the raw question plus session context into a structured query object
- detect ambiguity, missing context, medical entities, and recency cues

Allowed capabilities:

- Gemini structured output
- no external medical source access

### 8.2 Guideline Agent

Role:

- discover accessible guideline-backed recommendations and summarize them

Allowed connectors:

- one explicitly allowlisted guideline-discovery source in the first pass
- curated guideline fixtures only as dev/evaluation fallback if live retrieval is not yet stable
- broader guideline coverage added later

### 8.3 Literature Agent

Role:

- search and summarize journal literature and reviews
- identify recent evidence, study types, and population-specific findings

Allowed connectors:

- PubMed
- deferred later: Europe PMC
- deferred later: PubMed Central open-access full text where available

### 8.4 Drug Safety Agent

Role:

- retrieve indications, warnings, adverse effects, contraindications, and regulatory safety notes

Allowed connectors:

- DailyMed
- optional if clearly needed later: Drugs@FDA
- optional stretch: openFDA for secondary pharmacovigilance signals

### 8.5 Trials Agent

Role:

- identify ongoing, completed, and recent trials relevant to the question

Allowed connectors:

- ClinicalTrials.gov

### 8.6 Synthesizer Agent

Role:

- draft the answer from normalized evidence

Allowed inputs:

- parsed query
- normalized evidence items
- session context

Allowed tools:

- Gemini structured output or text generation
- no connector access

### 8.7 Verifier Agent

Role:

- validate evidence support, conflict handling, and abstention conditions

Allowed inputs:

- answer draft
- evidence items
- parsed query

Allowed tools:

- Gemini structured output
- no connector access

## 9. Capability Gating

The MVP does not need OS-level sandboxing or per-agent containers.

It does need capability gating:

- each specialist receives only its allowed connectors
- the synthesizer and verifier receive evidence objects, not raw browsing access
- the query parser cannot perform retrieval
- only the orchestrator can create and schedule subtasks

This keeps the system open-domain at the product level while constraining internal execution by capability.

## 9.1 Why LangGraph

LangGraph is the right orchestration choice for this system because the core workflow is not a linear request-response loop. It requires:

- explicit shared state
- conditional branching
- repeated specialist calls
- parallel and sequential execution
- safe pause points for clarification
- transparent execution traces

The architecture should use LangGraph as the control-flow runtime, not as a replacement for the rest of the backend architecture.

## 10. Orchestration Loop

The orchestration loop is implemented as a LangGraph state machine.

### 10.1 Run Lifecycle

Each user turn creates one `Run`.

Run phases:

1. ingest user turn and session context
2. normalize query
3. clarify if required
4. plan evidence gathering
5. execute independent tasks in parallel
6. aggregate evidence
7. assess evidence coverage
8. optionally schedule follow-up specialist tasks
9. stop when answerable or abstainable
10. synthesize
11. verify
12. persist response and run trace

### 10.1.3 Scaffold-First Runtime Milestone

Before broad real-source integration, the backend should support a fully deployable orchestration path using:

- real session and run persistence
- real LangGraph execution
- real response contracts
- mock specialist outputs through connector interfaces

This allows the system to demonstrate clarification, orchestration, synthesis, verification, and abstention behavior before every connector is complete.

### 10.1.1 Graph Nodes

Recommended initial nodes:

- `load_session_context`
- `normalize_query`
- `plan_evidence`
- `dispatch_specialists`
- `aggregate_evidence`
- `assess_coverage`
- `synthesize_answer`
- `verify_answer`
- `finalize_response`

### 10.1.2 Graph State

The LangGraph state object should contain:

- session identifiers
- current user message
- compact session context
- normalized query
- evidence plan
- pending specialist tasks
- completed task results
- normalized evidence items
- unresolved gaps
- coverage decision
- draft answer
- verification result
- final assistant response

### 10.2 Parallel vs Sequential Execution

Use parallel execution when subtasks are independent.

Example:

- guideline lookup
- broad literature search

Use sequential execution when later subtasks depend on prior outputs.

Example:

- first-pass literature search identifies a candidate experimental drug
- drug-safety agent is then called with that specific drug
- trials agent is then called for that same intervention

In LangGraph terms:

- independent first-pass specialist tasks can be emitted from the same planning state
- follow-up tasks should be scheduled only after `assess_coverage` decides the current evidence set still has material gaps

### 10.3 Stop Conditions

The orchestrator must stop when any of the following is true:

- evidence is sufficient to answer safely
- the verifier determines the answer should abstain
- a clarification question is required before continuing
- no new useful evidence is found in the last iteration
- maximum iteration count is reached
- maximum task count is reached

Recommended hard limits for the MVP:

- max orchestration iterations: 3
- max specialist tasks per run: 8
- max retry count for invalid structured output: 2

### 10.4 Clarification Interrupts

When clarification is required, the graph should stop at a stable checkpoint and return a `needs_clarification` response to the client.

On the next user turn:

- the session service merges the new context into the session state
- a new run resumes from the start with enriched session context

The MVP does not need full arbitrary graph resume across all nodes. It only needs deterministic checkpointing around major orchestration boundaries and safe handling of clarification turns.

## 11. Data Contracts

All model-facing and connector-facing data should use explicit Pydantic models.

### 11.1 Normalized Query

```python
class NormalizedQuery(BaseModel):
    raw_question: str
    normalized_question: str
    intent_summary: str
    scope: ScopeDecision
    needs_clarification: bool
    clarification_question: str | None
    ambiguity_notes: list[str]
    entities: list[QueryEntity]
    constraints: list[QueryConstraint]
    recency_focus: bool
    session_context_used: bool
    normalization_notes: list[NormalizationNote]
```

### 11.2 Evidence Plan

```python
class EvidencePlan(BaseModel):
    normalized_question: str
    primary_goal: str
    answer_strategy: str
    subquestions: list[PlannedSubquestion]
    retrieval_specs: list[RetrievalSpec]
```

### 11.3 Retrieval Spec

```python
class RetrievalSpec(BaseModel):
    spec_id: str
    lane: Literal["guideline", "literature", "drug_safety", "trials"]
    objective: str
    rationale: str
    query_text: str
    source_query: str
    focus_terms: list[str]
    desired_result_count: int
    priority: str
    depends_on: list[str]
```

### 11.4 Specialist Task

```python
class SpecialistTask(BaseModel):
    task_id: str
    agent_type: Literal["guideline", "literature", "drug_safety", "trials"]
    objective: str
    query_text: str
    source_query: str
    rationale: str | None
    focus_terms: list[str]
    priority: str
    desired_result_count: int
    depends_on: list[str]
```

### 11.5 Source Document

```python
class SourceDocument(BaseModel):
    source_id: str
    source_type: Literal["guideline", "review", "trial", "label", "registry", "study"]
    title: str
    url: str
    publication_date: date | None
    publisher: str | None
    abstract: str | None
    full_text: str | None
    metadata: dict[str, Any]
```

### 11.6 Evidence Item

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    source_type: str
    title: str
    url: str
    publication_date: date | None
    population: str | None
    intervention: str | None
    outcome: str | None
    key_claim: str
    claim_type: str | None
    applicability: str | None
    supports_question_dimensions: list[str]
    safety_notes: list[str]
    limitations: list[str]
    uncertainty_notes: list[str]
    evidence_strength: Literal["high", "moderate", "low", "unknown"]
    source_priority: int
    extracted_entities: list[str]
    question_role: str | None
    semantic_relevance: int | None
    include_in_answer: bool | None
    assessment_summary: str | None
```

### 11.7 Evidence Coverage Decision

```python
class EvidenceCoverageDecision(BaseModel):
    answerable_now: bool
    needs_follow_up: bool
    rationale: str
    remaining_gaps: list[str]
    follow_up_specs: list[RetrievalSpec]
```

### 11.8 Assistant Response

```python
class AssistantResponse(BaseModel):
    status: Literal["answered", "needs_clarification", "abstained"]
    answer: str | None
    clarification_question: str | None
    abstention_class: str | None
    abstention_reason: str | None
    evidence_summary: list[str]
    evidence_strength: Literal["high", "moderate", "low", "unknown"] | None
    limitations: list[str]
    citations: list[Citation]
    last_literature_check_at: datetime | None
```

### 11.9 Verification Result

```python
class VerificationResult(BaseModel):
    status: Literal["pass", "clarify", "abstain"]
    supported_claims: list[VerifiedClaim]
    unsupported_claims: list[str]
    conflicts: list[str]
    abstention_class: str | None
    abstention_reason: str | None
```

## 12. Storage Model

Use PostgreSQL from the start.

Core tables:

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

Table intent:

- `chat_sessions`: one conversation thread
- `chat_messages`: user and assistant turns
- `runs`: one orchestration attempt per user turn
- `run_steps`: each specialist invocation and synthesizer/verifier step
- `sources`: normalized source metadata
- `evidence_items`: normalized evidence extracted from sources
- `answer_claims`: atomic answer statements
- `claim_citations`: mapping from claims to evidence
- `eval_*`: benchmark definitions and scoring outputs

Redis usage:

- cache external source responses
- cache normalized source payloads
- optionally hold short-lived run execution state if later moving to workers

## 13. API Contract

### Session APIs

- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/messages`

### Chat API

- `POST /api/sessions/{session_id}/messages`

Request:

```json
{
  "role": "user",
  "content": "Latest treatment for drug-resistant TB in pregnancy, and major safety concerns."
}
```

Response:

```json
{
  "run_id": "uuid",
  "response": {
    "status": "answered",
    "answer": "...",
    "clarification_question": null,
    "abstention_class": null,
    "abstention_reason": null,
    "evidence_summary": ["..."],
    "evidence_strength": "moderate",
    "limitations": ["..."],
    "citations": [
      {
        "label": "1",
        "source_id": "src_123",
        "title": "Guideline title",
        "url": "https://...",
        "publication_date": "2026-01-10"
      }
    ],
    "last_literature_check_at": "2026-05-13T10:00:00Z"
  }
}
```

### Run Inspection APIs

- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/steps`

These are important for debugging and demo transparency.

### Evaluation APIs

- `POST /api/eval/runs`
- `GET /api/eval/runs/{eval_run_id}`

## 14. External Source Connectors

Each connector must:

- build source-specific queries
- fetch raw documents or metadata
- map results into `SourceDocument`
- expose deterministic errors
- avoid leaking provider-specific shapes into the orchestrator
- support fixture-backed or mock-backed development before live integration is complete

Planned connectors:

- PubMed
- ClinicalTrials.gov
- DailyMed if integration proves straightforward in the first implementation pass
- one narrow guideline connector or curated guideline fixture layer
- deferred later: Europe PMC
- deferred later: PubMed Central open-access fetcher
- deferred later: broader guideline-source adapters

Connector priority for the MVP:

1. mock connectors for all retrieval-specialist roles
2. PubMed
3. ClinicalTrials.gov
4. DailyMed if low-friction
5. one narrow guideline source or curated guideline fixture support

Guideline retrieval should be allowlisted to public evidence-based sources. The MVP should not expose unrestricted web search, and Playwright should be treated as a selective exploration/fallback tool rather than the foundation of retrieval.

## 15. Structured Output Strategy

Use Gemini structured output with Pydantic models for:

- query parsing
- specialist task planning
- evidence extraction
- synthesis metadata
- verification results

Rules:

- keep each schema narrow
- validate every response
- retry invalid outputs up to two times
- drop malformed evidence objects rather than silently trusting them
- separate extraction from synthesis

LangGraph nodes should treat invalid structured output as a node-level failure that can be retried or surfaced safely, rather than leaking malformed objects into downstream nodes.

## 16. Safety and Refusal Enforcement

The final response must pass the verifier gate.

Possible outcomes:

- `answered`
- `needs_clarification`
- `abstained`

Abstention classes:

- insufficient evidence
- conflicting evidence
- missing clinical context
- coverage gap
- recency gap
- ambiguous query

The verifier is authoritative over the final status.

## 17. Observability

Every run must record:

- input message
- session context snapshot
- parsed query
- planned tasks
- task execution timings
- source documents retrieved
- evidence items extracted
- synthesis output
- verification output
- final response

Required logging fields:

- `session_id`
- `run_id`
- `task_id`
- `agent_type`
- `connector`
- `source_id`
- `latency_ms`
- `status`

Additional graph-level metadata:

- `graph_node`
- `graph_iteration`
- `checkpoint_id`
- `dependency_task_ids`

## 18. Evaluation Architecture

The evaluation system is part of the product, not an afterthought.

Components:

- benchmark question registry
- expected-behavior annotations
- evaluation runner
- evaluator scoring store
- reviewer-facing report generation

Supported benchmark strata:

- direct lookup
- multi-source synthesis
- drug safety
- latest-evidence prompts
- ambiguous prompts
- clarification-required flows
- should-refuse prompts
- adversarial nonsense prompts

## 19. Frontend Integration Contract

The frontend should treat the backend as the source of truth for answer state.

Required frontend states:

- waiting
- answered
- clarification needed
- abstained
- error

The frontend should render citations and limitations as first-class UI elements, not hidden metadata.

## 20. Scalability Path

The MVP is intentionally simple in deployment, but the architecture must support later scale-up.

### Stage 1: MVP

- modular monolith
- in-process LangGraph runtime
- async connector fan-out
- deployable backend scaffold before broad connector completion

### Stage 2: Throughput Scale

- introduce a queue-backed worker pool for expensive specialist runs
- keep API service responsible only for session and run management
- move connector-heavy tasks into workers

### Stage 3: Selective Service Extraction

Potential extraction candidates:

- retrieval worker service
- evaluation runner service
- source indexing or caching service

Extraction triggers:

- sustained latency bottlenecks
- connector rate-limit pressure
- need for horizontal worker scaling
- operational need for separate deployment cadence

LangGraph remains useful even after worker extraction because the graph can continue to define orchestration semantics while individual node execution moves behind queue-backed workers.

## 21. Non-Goals for Architecture

The MVP architecture should not include:

- microservices by default
- per-agent containers
- event bus driven workflows
- unrestricted web browsing
- persistent longitudinal memory across sessions
- overuse of LangGraph for non-workflow concerns such as persistence, connector code, or generic utilities

These can be added later only if a concrete scaling or compliance need appears.
