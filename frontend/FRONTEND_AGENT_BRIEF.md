# Frontend Agent Brief

This brief is only for frontend-to-backend integration.

## Goal

Build the frontend against the current Chiron backend contract.

Do not invent backend routes.
Do not add frontend-side medical logic.
Do not assume every assistant response is a plain text answer.

## Backend Base URL

Default local backend:

- `http://127.0.0.1:8000`

API prefix:

- `/api`

Recommended frontend env var:

- `VITE_API_BASE_URL=http://127.0.0.1:8000/api`

The backend already allows CORS from:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Required Endpoints

### `GET /api/health`

Use for connectivity checks.

Response shape:

```json
{
  "status": "ok",
  "service": "Chiron Backend",
  "llm_mode": "heuristic"
}
```

### `GET /api/sessions`

Returns all sessions.

Response shape:

```json
[
  {
    "id": "string",
    "title": "string | null",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
]
```

### `POST /api/sessions`

Create a session.

Request:

```json
{
  "title": "string | null"
}
```

Response shape is the same as `GET /api/sessions`.

### `GET /api/sessions/{session_id}/messages`

Returns all stored messages for a session.

Response:

```json
[
  {
    "id": "string",
    "session_id": "string",
    "role": "user | assistant",
    "content": "string",
    "metadata_json": {},
    "created_at": "datetime"
  }
]
```

Important:

- user messages use `content`
- assistant messages store the structured response in `metadata_json`
- assistant `content` is only a readable text fallback, not the main source of truth

### `POST /api/sessions/{session_id}/messages`

Submit a user message and trigger a backend run.

Request:

```json
{
  "role": "user",
  "content": "string"
}
```

Response:

```json
{
  "run_id": "string",
  "response": {
    "status": "answered | needs_clarification | abstained",
    "answer": "string | null",
    "clarification_question": "string | null",
    "abstention_class": "string | null",
    "abstention_reason": "string | null",
    "evidence_summary": ["string"],
    "evidence_strength": "high | moderate | low | unknown | null",
    "limitations": ["string"],
    "citations": [
      {
        "label": "string",
        "source_id": "string",
        "title": "string",
        "url": "string",
        "publication_date": "date | null",
        "source_type": "string | null",
        "publisher": "string | null",
        "snippet": "string | null"
      }
    ],
    "evidence_items": [
      {
        "evidence_id": "string",
        "source_id": "string",
        "source_type": "string",
        "title": "string",
        "url": "string",
        "publication_date": "date | null",
        "publisher": "string | null",
        "population": "string | null",
        "intervention": "string | null",
        "outcome": "string | null",
        "key_claim": "string",
        "claim_type": "string | null",
        "applicability": "string | null",
        "supports_question_dimensions": ["string"],
        "safety_notes": ["string"],
        "limitations": ["string"],
        "uncertainty_notes": ["string"],
        "evidence_strength": "string",
        "source_priority": 0,
        "extracted_entities": ["string"]
      }
    ],
    "last_literature_check_at": "datetime | null"
  }
}
```

### `GET /api/runs/{run_id}/steps`

Optional, but useful for loading/progress/debug views.

Response:

```json
[
  {
    "id": "string",
    "run_id": "string",
    "node_name": "string",
    "step_order": 1,
    "status": "completed",
    "input_json": {},
    "output_json": {},
    "created_at": "datetime"
  }
]
```

## Assistant States

The frontend must support exactly these response states:

- `answered`
- `needs_clarification`
- `abstained`

Expected behavior:

- `answered`
  - render `answer`
  - render `citations`
  - render `evidence_items`
  - render `limitations`
  - render `evidence_strength`

- `needs_clarification`
  - render `clarification_question`
  - continue in the same session

- `abstained`
  - render `abstention_reason`
  - render `abstention_class`
  - optionally render `limitations`

## Session Loading Behavior

Use this flow:

1. load sessions with `GET /api/sessions`
2. when a session is selected, load messages with `GET /api/sessions/{session_id}/messages`
3. when the user sends a message:
   - append the user message locally
   - call `POST /api/sessions/{session_id}/messages`
   - append the returned assistant response

If no session exists yet:

1. create it with `POST /api/sessions`
2. then submit the message

## Message Mapping

Map backend messages like this:

- backend `role=user` -> user chat bubble from `content`
- backend `role=assistant` -> assistant message from `metadata_json`

For assistant history reload:

- use `metadata_json.run_id` if present
- otherwise fall back to the message id for local keys

## Current Reality

The backend is already live and tested.

What exists now:

- session APIs
- message APIs
- run-step API
- CORS for Vite dev
- structured evidence-rich assistant responses

What the frontend does not need to solve:

- orchestration
- citation generation
- evidence ranking
- medical reasoning

## Current Frontend Status

There is already a frontend app in `frontend/`.

It already contains:

- a shell
- session list
- conversation pane
- evidence panel
- API client layer

So this is not a greenfield brief.

The frontend builder should:

- treat the existing `frontend/` app as the base
- keep the API integration isolated in the client layer
- avoid breaking the current backend contract

## Acceptance Check

The frontend integration is correct when:

1. the app can load sessions from the backend
2. the app can load messages for a selected session
3. the app can submit a user question to the backend
4. the app can render all three assistant states
5. the app can show citations and evidence items from the response payload
6. the app can recover cleanly from backend/network errors
