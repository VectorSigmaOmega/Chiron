# Chiron

Chiron is an evidence-grounded medical question answering system for clinicians.
It accepts open-ended medical queries and responds in one of three ways:

- `answered` with citations and limitations
- `needs_clarification` when the prompt is underspecified
- `abstained` when the evidence is insufficient, conflicting, outdated, or out of scope

The goal is not to imitate a general chatbot. The goal is to make the system
useful only when it can stay grounded.

## Live Demo

- App: `https://chiron.abhinash.dev`
- API health: `https://chiron.abhinash.dev/api/health`

## Why Chiron Exists

Medical professionals need fast access to current information, but they cannot
depend on unconstrained LLM output for clinical questions. Chiron is designed
around a stricter contract:

- retrieve from trusted medical and regulatory sources
- synthesize only from retrieved evidence
- preserve citations and provenance
- refuse safely when the system cannot support an answer

## Current MVP

The repository currently contains a deployable MVP with:

- a React frontend
- a FastAPI backend
- LangGraph-based orchestration
- persistent sessions, messages, runs, and run steps
- real source integrations for:
  - PubMed
  - ClinicalTrials.gov
  - DailyMed
- a curated guideline fixture path for demo-time guidance coverage
- Gemini-backed parsing, synthesis, and verification
- deterministic heuristic fallback paths
- a benchmark harness with latency reporting

## System Behavior

At runtime, Chiron follows an evidence workflow:

1. Parse the user question into a structured medical query.
2. Decide whether clarification is needed.
3. Plan specialist retrieval tasks.
4. Retrieve evidence from supported sources.
5. Normalize evidence into typed evidence items.
6. Synthesize a grounded draft answer.
7. Verify support, recency, scope, and applicability.
8. Return an answer, clarification request, or abstention.

## Repository Structure

```text
frontend/   React + Vite client
backend/    FastAPI, LangGraph orchestration, connectors, evaluation runner
PRDs/       product requirements
docs/       architecture and implementation notes
eval/       benchmark cases and generated reports
```

## Tech Stack

### Frontend

- React
- TypeScript
- Vite

### Backend

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy
- LangGraph
- Google Gemini API
- SQLite by default for zero-setup local runs

## Local Development

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
uv sync --all-groups
uv run uvicorn app.main:app --reload
```

Backend health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## Configuration

The backend supports two runtime styles:

- `heuristic` mode for low-friction local or benchmark runs
- `gemini` mode for structured query parsing, synthesis, and verification

Useful environment variables:

```bash
CHIRON_LLM_MODE=heuristic|gemini
CHIRON_GEMINI_MODEL=gemini-3-flash-preview
CHIRON_LITERATURE_CONNECTOR_MODE=mock|pubmed
CHIRON_TRIALS_CONNECTOR_MODE=mock|clinicaltrials
CHIRON_DRUG_SAFETY_CONNECTOR_MODE=mock|dailymed
CHIRON_GUIDELINE_CONNECTOR_MODE=mock|fixture
```

## Evaluation

Chiron includes a benchmark harness in `backend/app/evaluation/runner.py`.

Recent benchmark modes used during development:

- `heuristic_mock`
- `heuristic_mixed_real`
- `gemini_mixed_real`

`heuristic_mixed_real` means:

- heuristic parse/synthesis/verification
- real retrieval connectors for PubMed, ClinicalTrials.gov, and DailyMed
- fixture-based guideline support

This mode has been useful as a latency-aware baseline against the Gemini path.

## Automation

GitHub Actions is configured for:

- `CI`: backend tests, frontend typecheck/build, and a deterministic benchmark smoke run
- `CD`: artifact-based deployment to the production VPS on `main`

The deployment path matches the current infrastructure:

- frontend is built in GitHub Actions and copied to the VPS as static assets
- backend is refreshed on the VPS and restarted via `systemd`
- nginx continues to serve the frontend and proxy `/api`

## Current Limits

This is an MVP, not production clinical decision support.

Known constraints:

- guideline coverage is still narrow
- broad live guideline ingestion is not implemented
- answer quality is improving, but not production-grade
- verification is stronger than a generic chatbot, but still evolving
- no EHR integration
- no patient longitudinal memory across sessions

## Documentation

- Product requirements: [PRDs/PRD.md](PRDs/PRD.md)
- Safety and evaluation policy: [PRDs/SAFETY_EVAL.md](PRDs/SAFETY_EVAL.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Backend notes: [backend/README.md](backend/README.md)
- Frontend notes: [frontend/README.md](frontend/README.md)

## Status

Chiron is already deployable and live, but still in active development.
The current focus is improving retrieval quality, evidence extraction,
verification, and benchmark coverage.
