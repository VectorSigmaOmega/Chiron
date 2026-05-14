# Implementation Decisions Review

A validation pass over `IMPLEMENTATION_DECISIONS_QA.md` against `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, the PRDs, and the assignment context. Captures what is consistent, what is questionable, and what is missing — so it survives context compaction and can be acted on later.

## Verdict

The 90-question decision sheet is **internally consistent with `ARCHITECTURE.md` and `IMPLEMENTATION_PLAN.md`** on the load-bearing items: three-state response contract, six abstention classes, four retrieval specialists, the 10-node graph, capability gating, separation of session vs graph state, and structured outputs at typed boundaries. All schemas (Q55–Q60) match Section 11 of the architecture verbatim.

The problems are not contradictions — they are **decisions that look fine in isolation but become unrealistic when combined under take-home time and a placement-demo audience**. Listed in priority order.

---

## Major issues to revisit before coding starts

### 1. The guideline allowlist (Q36) is aspirational, not buildable
"Start with WHO, NICE, CDC, NIH" reads cleanly on paper. In practice:

- WHO publishes guidelines as PDF; no machine-readable API.
- NICE has structured data but commercial-use terms.
- CDC has scrape-friendly pages but no unified API.
- NIH is not one source — it spans MedlinePlus, NHLBI, NIDDK, etc.

A realistic MVP gets **one** working guideline connector (most likely CDC or a curated guideline JSON snapshot shipped in `eval/fixtures/`). Lock Q36 to "one public guideline source, allowlist expandable post-MVP" and pick the specific one now.

### 2. Six connectors is too many for the assignment window
Q35 mandates PubMed + Europe PMC + PMC OA + ClinicalTrials.gov + DailyMed + guidelines. Phase 2 of the plan asks for all six before the orchestration loop exists.

Recommend dropping the MVP-required set to **PubMed + ClinicalTrials.gov + DailyMed + 1 guideline source**, and treating Europe PMC / PMC OA as Phase-8 hardening. Europe PMC overlaps heavily with PubMed and adds full-text only in some cases — high cost, marginal MVP signal.

### 3. India / ICMR alignment vs Q2's "global first"
Project memory flags that Jubilant is Indian pharma and ICMR / Indian drug naming likely matter to evaluators. Q2 defers geography. These may be in tension — if the reviewer expects to see Indian-context awareness, "global-first" is the wrong default.

This deserves a direct user decision before locking.

### 4. "Gemini" (Q18) is too loose
There is a material reliability gap between Gemini 2.5 Pro and 2.5 Flash on structured outputs, especially for the query parser and verifier. Lock the specific model per node (e.g., 2.5 Pro for parse/plan/verify, Flash for evidence extraction where throughput matters) and the JSON-mode flag, before coding.

### 5. Evaluation scoring methodology is unspecified (Q72–Q76)
The benchmark, strata, and acceptance criteria are well-defined. What's missing: **who scores each run.** Options are (a) rule-based checks on output shape + citation presence, (b) LLM-as-judge with a fixed rubric, (c) hand-grading. Section 9 of `SAFETY_EVAL.md` says "rubric-based" but does not pick a scorer. For 40–60 questions, (a)+(b) combined is the realistic choice. Lock this.

### 6. Session compaction is named but not designed (Q44, Q47)
Both say "compact structured context derived from the conversation," neither says how it's produced (LLM summarization? rule-based slot-filling from prior `ParsedQuery` entities?), when it updates, or what shape it has. This is the seam between the session service and the orchestrator — needs a concrete contract before Phase 1.

---

## Medium issues

### 7. "Specialist" is overloaded (Q24 vs Q25 vs Q54)
Q25 lists 7 specialists (parser, guideline, literature, drug-safety, trials, synthesizer, verifier). Q54's `agent_type` enum has 4 (guideline, literature, drug_safety, trials). Architecture §8 lists 7 agents. Vocabulary problem, not a logic problem, but it will confuse implementers. Recommend two distinct terms: **retrieval specialists** (the 4 in Q54) and **pipeline nodes** (parser, synthesizer, verifier).

### 8. Evidence ranking has no owner (Q40)
The policy (authority → type → recency → applicability) is good, but no document says which component computes the rank. Logical home is the evidence normalizer (Architecture §7.6) — say so explicitly, and decide whether ranking is a stable sort by `evidence_strength` + tiebreaker fields, or an LLM scoring step.

### 9. Postgres + Alembic for a take-home demo (Q14–Q15)
For a placement assignment that will likely run from one laptop with one reviewer, SQLite via SQLAlchemy is operationally lighter (no docker-compose, no migrations, no port collisions). Postgres earns its keep when concurrent writes and rich types matter — neither applies here. Defaulting to SQLite for dev and keeping Postgres compatibility via SQLAlchemy is a low-risk simplification.

### 10. No decision on semantic retrieval
No mention of embeddings, vector index, or reranking. For "latest treatment for X" queries, source-native keyword search (PubMed eutils) plus LLM extraction is often weak on recall. Either acknowledge "MVP relies on source-native search; no semantic layer" as a deliberate limitation, or commit to a minimal embedding/rerank step for `aggregate_evidence`. Silence here will be a question reviewers ask.

### 11. In-memory checkpointer + process restart (Q34, Q90)
"In-memory first" is fine for a demo, but means a crashed API process loses any in-flight run. Call it out as a known limit and pair it with run records being durable in Postgres (which they already are per Q48), so a restart loses progress but not the trace.

### 12. Graph state size (Q45)
Holding `completed_task_results`, `normalized_evidence_items`, and `draft_answer` inside LangGraph state will bloat each transition snapshot. Recommend keeping **IDs only** in graph state, with a per-run in-memory store (or Postgres) for the full objects.

### 13. Preprint exclusion (Q41) needs a connector-level filter
PubMed and Europe PMC both index preprints. Without explicit type filters at the connector layer, "no preprints" will leak. One-line filter — note it in the connector contract.

---

## Decisions that look fine but are worth confirming

- **Q21 LangGraph as runtime.** Justified if the demo features the graph trace as a trust artifact. If the demo will not surface the graph, a plain async state machine would do the same work with fewer deps. Worth asking whether the trace is part of the pitch.
- **Q32 hard limits (3 iterations / 8 tasks / 2 retries).** Reasonable. Make sure the verifier-to-abstention path is short enough that all 3 iterations aren't burned before reaching it.
- **Q48 table count (11).** `answer_claims` and `claim_citations` are valuable for FR8 (citation binding), but can collapse into a single `answer_claims_with_citations` for MVP if constrained.

---

## Decisions that are missing entirely

Adding short Q&As for these would close the spec:

- **No-auth posture for MVP** — explicit "no auth, no user accounts" decision.
- **Rate limiting / NCBI eutils API key handling** — required for PubMed, real impact on eval-run throughput.
- **Connector caching policy** — Q16 says Redis optional, but for repeated eval runs PubMed will be re-hit unless something caches. Either Redis or a SQLite-backed `httpx-cache` should be picked.
- **LLM cost budget per run / per eval batch** — easy to overspend during benchmark runs.
- **Error contract for the chat API** — Q63 says "stable contract" but there is no documented shape for transport errors (5xx, timeout) as opposed to product-level `error` state.
- **Date awareness mechanism** — recency-sensitive prompts (`SAFETY_EVAL.md` §10) require the system to know "today." Lock how `today` is injected into prompts (system message? `ParsedQuery` field?).
- **Frontend session ID provenance** — backend-generated UUID assumed but not stated.

---

## What is already strong and should be treated as locked

Coherent across all three docs; not worth revisiting:

- Three-state response contract (`answered` / `needs_clarification` / `abstained`)
- Six-class abstention taxonomy
- Capability gating instead of sandboxing
- Synthesizer and verifier have no connector access
- One run per user turn; clarification = new run with enriched session context
- Typed Pydantic contracts at every model boundary, retry-twice-then-fail policy
- Evaluation harness in-MVP, 40–60 questions, stratified
- Modular monolith with `frontend/` + `backend/` + `eval/`

---

## Suggested next actions

1. Draft tightened replacement answers for Q2, Q18, Q35, Q36, Q44/Q47, and Q72–Q76 in the same Q/A format and paste them into `IMPLEMENTATION_DECISIONS_QA.md`.
2. Sketch the actual LangGraph state and node interfaces (Python signatures, not implementations) so Phase 3/4 has a concrete starting shape.
3. Confirm with the user whether ICMR / Indian context is part of the evaluators' expectations before locking Q2.
