# Chiron Implementation Plan

## 1. Goal

Build an MVP of `Chiron` that can:

- accept an open-domain medical question
- ask for clarification when needed
- retrieve evidence from trusted sources using specialist agents
- synthesize an answer with citations and dates
- abstain when the evidence is insufficient, conflicting, or out of scope
- demonstrate correctness through an evaluation harness

The frontend is delegated separately. This plan focuses on backend-first delivery with a stable API contract for frontend integration.

## 2. Delivery Strategy

Build in vertical slices:

1. lock contracts and scaffolding
2. get one end-to-end query path working
3. add more connectors and specialist depth
4. add verification and evaluation
5. harden observability and demo readiness

Do not start by building every connector or every agent in parallel.

## 3. Phase 0: Repository and Environment Foundation

### Tasks

- create `frontend/`, `backend/`, `docs/`, and `eval/` folders
- initialize backend project and dependency management
- add FastAPI app skeleton
- add LangGraph dependency and orchestration package scaffold
- add environment-variable configuration
- set up PostgreSQL and Redis via local development tooling
- add linting, formatting, and test tooling
- document local setup

### Deliverables

- bootable backend service
- local development environment
- dependency lockfile
- baseline CI checks

### Acceptance Criteria

- backend starts locally with one health endpoint
- tests run locally and in CI
- developers can start Postgres and Redis with a single documented command

## 4. Phase 1: Core Schemas, Persistence, and Session APIs

### Tasks

- implement Pydantic schemas for parsed queries, tasks, sources, evidence, responses, and verification
- define SQLAlchemy models and initial Alembic migrations
- implement session and message persistence
- implement basic session APIs
- implement run and run-step persistence models

### Deliverables

- database schema
- session creation endpoint
- message storage endpoint
- run tracking foundation

### Acceptance Criteria

- a session can be created and fetched
- user and assistant messages are stored correctly
- a run record can be created and linked to a message
- schema validation rejects malformed payloads

## 5. Phase 2: Source Connector Layer

### Tasks

- implement connector interface and common error model
- build PubMed connector
- build Europe PMC connector
- build PMC open-access fetcher
- build ClinicalTrials.gov connector
- build DailyMed connector
- build one guideline-source adapter abstraction
- add connector tests with recorded fixtures or deterministic mocks

### Deliverables

- working connector modules
- normalized `SourceDocument` outputs
- connector test suite

### Acceptance Criteria

- each connector returns normalized source records
- connector failures surface deterministic error codes
- connector tests pass without live network dependence when replay fixtures are used

## 6. Phase 3: Query Parsing and Specialist Task Planning

### Tasks

- implement the query parser using Gemini structured outputs
- implement clarification detection
- implement information-need extraction
- implement specialist task planner
- define LangGraph state schema
- scaffold core graph nodes and edges
- add schema validation and retry logic for model outputs
- define task dependency semantics

### Deliverables

- parsed query service
- task planner service
- graph state and node skeleton
- clarification decision path

### Acceptance Criteria

- ambiguous prompts reliably produce clarification questions
- direct prompts produce structured task plans
- the graph can compile and execute through parse and plan stages
- invalid model output is retried and then surfaced safely if still invalid

## 7. Phase 4: Specialist Agents and Orchestration Loop

### Tasks

- implement guideline agent
- implement literature agent
- implement drug-safety agent
- implement trials agent
- enforce capability gating by dependency injection of allowed connectors
- implement LangGraph run state and checkpointer integration
- implement parallel execution for independent specialist nodes
- implement sequential re-planning through graph transitions
- implement stop conditions and iteration limits

### Deliverables

- working specialist agents
- compiled LangGraph workflow
- run-step tracing

### Acceptance Criteria

- one question can trigger multiple specialists
- the orchestrator can run first-pass parallel tasks and then second-pass follow-up tasks
- run traces show task order, dependencies, and outputs
- LangGraph state transitions are inspectable during test runs
- loop termination works under both success and no-progress conditions

## 8. Phase 5: Evidence Normalization, Synthesis, and Verification

### Tasks

- implement evidence normalizer
- deduplicate sources and evidence items
- implement synthesizer using normalized evidence only
- implement verifier with claim-support checks
- implement refusal and clarification finalization logic
- map verified claims to citations in the final response

### Deliverables

- normalized evidence pipeline
- final answer composer
- verifier gate

### Acceptance Criteria

- final responses include citations and source dates
- unsupported answer claims are blocked from reaching the user
- abstention classes are emitted correctly
- clarification, answer, and abstention all use the same response contract

## 9. Phase 6: Chat API Completion and Frontend Contract Freeze

### Tasks

- finalize `POST /api/sessions/{session_id}/messages`
- implement run inspection endpoints
- document response shapes for frontend integration
- define loading, error, clarification, answered, and abstained states
- add example payloads for frontend consumers

### Deliverables

- stable chat API
- run-debug APIs
- frontend integration spec

### Acceptance Criteria

- frontend team can integrate without reading backend internals
- one message endpoint returns all required states through a stable schema
- run inspection is sufficient for debugging demos

## 10. Phase 7: Evaluation Harness

### Tasks

- create benchmark question dataset in `eval/`
- annotate expected behavior for each question
- implement evaluation runner
- implement scoring storage
- generate reviewer-facing evaluation report
- include multi-turn clarification scenarios

### Deliverables

- benchmark set
- evaluation execution path
- report artifact

### Acceptance Criteria

- benchmark runs can be launched programmatically
- results are stored and inspectable
- evaluation report includes question, expected behavior, actual behavior, and evidence used

## 11. Phase 8: Hardening and Demo Readiness

### Tasks

- add caching for connector responses
- tighten timeout handling and retries
- improve source-date handling for recency-sensitive queries
- add seeded demo sessions
- capture sample run traces for presentation
- document the graph and node roles for reviewers
- add operational metrics and structured logs

### Deliverables

- more stable latency
- demo script support
- observability improvements

### Acceptance Criteria

- common demo queries complete within acceptable latency
- logs and traces are sufficient to explain system behavior live
- seeded examples cover answer, clarification, and abstention flows

## 12. Test Plan

### Unit Tests

- schema validation
- connector normalization
- evidence-strength mapping
- refusal classification
- stop-condition logic

### Integration Tests

- end-to-end answer flow
- clarification flow
- abstention flow
- multi-pass orchestration flow
- citation binding flow

### Evaluation Tests

- benchmark set across all strata
- adversarial fake-entity prompts
- recency-sensitive prompts
- clarification-follow-up sequences

## 13. API and Contract Decisions

These decisions are locked for implementation:

- backend is a FastAPI service
- frontend and backend live in separate folders
- backend owns session state and final response contract
- specialist agents are source-type based, not symptom/drug/journal buckets
- tool access is restricted by capability gating, not OS-level sandboxing
- LangGraph is the orchestration runtime; connectors, persistence, and verification remain normal application modules
- the final response status must always be one of `answered`, `needs_clarification`, or `abstained`
- the verifier is the final gate before any assistant response is persisted

## 14. Recommended Execution Order

If only one engineer is implementing backend first:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4 with only guideline and literature agents first
6. Phase 5
7. add drug-safety and trials depth
8. Phase 6
9. Phase 7
10. Phase 8

If multiple engineers are available:

- one owner for persistence and API foundation
- one owner for connectors
- one owner for orchestration and agent logic
- one owner for evaluation harness

## 15. Definition of Done for MVP

The MVP is done when all of the following are true:

- a user can ask a medical question through the chat API
- the system can clarify ambiguous prompts
- the system can produce grounded answers from at least the core source set
- the system abstains correctly when evidence is insufficient or outside scope
- every answer includes citations and source dates
- the evaluation harness can run a benchmark set and produce an inspectable report
- the frontend team has a stable contract to integrate against

## 16. Deferred Work

Deliberately deferred until after MVP:

- per-agent worker processes
- distributed queues
- persistent cross-session case memory
- unrestricted web search
- provider-agnostic multi-LLM routing
- advanced formal evidence grading frameworks
