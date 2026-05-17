# Chiron Backend

Deployable backend scaffold for the `Chiron` medical evidence assistant.

## What Works Now

- FastAPI service
- LangGraph orchestration runtime
- session, message, run, and run-step persistence
- structured assistant response states:
  - `answered`
  - `needs_clarification`
  - `abstained`
- mock-backed deployable flow by default
- optional real connectors for:
  - PubMed
  - ClinicalTrials.gov
  - DailyMed
- narrow guideline support via curated fixture connector

## Local Run

```bash
cd backend
uv sync --all-groups
uv run uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## Default Behavior

The backend runs in a zero-manual-setup local mode by default:

- SQLite database
- heuristic orchestration mode
- mock connectors

This keeps the scaffold deployable without API keys or external services.

## Connector Modes

Environment variables:

```bash
CHIRON_LITERATURE_CONNECTOR_MODE=mock|pubmed
CHIRON_TRIALS_CONNECTOR_MODE=mock|clinicaltrials
CHIRON_DRUG_SAFETY_CONNECTOR_MODE=mock|dailymed
CHIRON_GUIDELINE_CONNECTOR_MODE=mock|fixture
```

Optional PubMed tuning:

```bash
CHIRON_PUBMED_API_KEY=...
CHIRON_PUBMED_EMAIL=you@example.com
```

## Example: Enable Real Sources

```bash
export CHIRON_LITERATURE_CONNECTOR_MODE=pubmed
export CHIRON_TRIALS_CONNECTOR_MODE=clinicaltrials
export CHIRON_DRUG_SAFETY_CONNECTOR_MODE=dailymed
export CHIRON_GUIDELINE_CONNECTOR_MODE=fixture
uv run uvicorn app.main:app --reload
```

## Test Suite

```bash
cd backend
uv run pytest
```

The suite covers:

- API flows
- PubMed connector
- ClinicalTrials.gov connector
- DailyMed connector
- guideline fixture connector

## Current Scope Limits

- guideline retrieval is currently fixture-based rather than broad live scraping
- synthesis is intentionally simple and conservative
- verification is scaffold-grade, not production-grade
- no unrestricted web search
- no persistent cross-session memory
