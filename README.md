# Chiron

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/VectorSigmaOmega/Chiron/actions/workflows/ci.yml/badge.svg)](https://github.com/VectorSigmaOmega/Chiron/actions/workflows/ci.yml)
[![CD](https://github.com/VectorSigmaOmega/Chiron/actions/workflows/cd.yml/badge.svg)](https://github.com/VectorSigmaOmega/Chiron/actions/workflows/cd.yml)
[![Live Demo](https://img.shields.io/badge/demo-live-0a7f5a)](https://chiron.abhinash.dev)

Chiron is an evidence-grounded medical research assistant designed for clinicians.
It helps users ask open-ended medical questions and get back answers that are tied
to cited evidence, with clear limits when the system cannot support a safe response.

The project is built around a simple idea: in medical workflows, honesty is more
important than fluency. A useful system is not one that always replies. It is one
that retrieves well, cites clearly, and refuses when the evidence is weak,
conflicting, outdated, or outside scope.

## Demo

- [Open the app](https://chiron.abhinash.dev)
- [API health endpoint](https://chiron.abhinash.dev/api/health)

## Overview

Chiron explores a safer architecture for medical question answering than a
general-purpose chatbot. Instead of generating free-form responses first and
justifying them later, it is built to:

- retrieve from trusted medical and regulatory sources
- preserve provenance and citation metadata
- synthesize only from retrieved evidence
- surface uncertainty and limitations
- abstain when a grounded answer cannot be supported

This repository contains the current MVP: a working full-stack system with a live
deployment, benchmark harness, source connectors, and deployment automation.

## What’s In The Repo

- `frontend/` — React + Vite client
- `backend/` — FastAPI backend, LangGraph orchestration, connectors, evaluation runner
- `PRDs/` — product requirements and scope
- `docs/` — architecture and implementation notes
- `eval/` — benchmark cases and generated reports

## Current MVP

The current build includes:

- a live web frontend
- a deployable backend service
- LangGraph-based orchestration
- persistent sessions, messages, runs, and run steps
- real connectors for:
  - PubMed
  - ClinicalTrials.gov
  - DailyMed
- a curated guideline fixture path
- Gemini-backed parsing, synthesis, and verification
- heuristic fallback paths
- benchmark and latency reporting
- CI/CD via GitHub Actions

## Architecture

At a high level, Chiron follows an evidence workflow:

1. Parse the question into a structured medical query.
2. Decide whether more context is required.
3. Plan evidence retrieval tasks.
4. Retrieve and normalize source material.
5. Synthesize a grounded draft.
6. Verify support, scope, and applicability.
7. Return a supported answer or a constrained refusal.

The system is intentionally designed as a modular monolith for the MVP, with a
separate frontend and backend and explicit seams for source connectors, specialist
workers, verification, and evaluation.

## Technology

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

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## Automation

GitHub Actions is configured for:

- `CI` — backend tests, frontend typecheck/build, and benchmark smoke checks
- `CD` — artifact-based deployment to the production VPS

The production deployment currently serves:

- frontend static assets through `nginx`
- backend API through `uvicorn` + `systemd`

## Status

Chiron is live and deployable, but still clearly an MVP. The main remaining work
is not plumbing. It is answer quality: stronger retrieval, richer evidence
extraction, better verification, and broader evaluation coverage.

## Documentation

- [Product requirements](PRDs/PRD.md)
- [Safety and evaluation policy](PRDs/SAFETY_EVAL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Backend notes](backend/README.md)
- [Frontend notes](frontend/README.md)

## License

This project is licensed under the [MIT License](LICENSE).
