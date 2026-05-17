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

## Gemini Mode

To enable Gemini-backed query parsing, synthesis, and verification:

```bash
cp .env.example .env
```

Recommended default:

```bash
CHIRON_LLM_MODE=gemini
CHIRON_GEMINI_MODEL=gemini-3-flash-preview
```

Why this default:

- `gemini-3-flash-preview` is Google's current general-purpose Gemini 3 text model with structured outputs support.
- `gemini-3.1-flash-lite` is the lower-cost Lite line and is better treated as a later optimization for cheaper substeps, not the default model for safety-sensitive synthesis and verification.

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

## Benchmark Harness

Run the small benchmark set in deterministic scaffold mode:

```bash
cd backend
CHIRON_LLM_MODE=heuristic \
CHIRON_LITERATURE_CONNECTOR_MODE=mock \
CHIRON_TRIALS_CONNECTOR_MODE=mock \
CHIRON_DRUG_SAFETY_CONNECTOR_MODE=mock \
CHIRON_GUIDELINE_CONNECTOR_MODE=mock \
uv run python -m app.evaluation.runner
```

This writes a JSON report to `eval/reports/latest.json`.

## Current Scope Limits

- guideline retrieval is currently fixture-based rather than broad live scraping
- synthesis is intentionally simple and conservative
- verification is scaffold-grade, not production-grade
- no unrestricted web search
- no persistent cross-session memory
