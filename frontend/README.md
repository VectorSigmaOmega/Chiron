# Chiron — Frontend

A grounded medical evidence assistant. Chiron answers clinical questions only
from trusted, cited evidence — and abstains, in a structured way, when it cannot
support a safe answer.

## Stack

- React 18 + TypeScript
- Vite
- No UI framework — a small hand-built design system (`src/styles/global.css`)

## Running

```bash
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` (a CORS-allowed origin).

The app talks to the Chiron backend at `http://127.0.0.1:8000/api` by default.
To point elsewhere, copy `.env.example` to `.env` and set `VITE_API_BASE_URL`.

The backend does not need to be running to load the UI — Chiron degrades
gracefully and shows a clear offline state until it can reach the API.

## Structure

```
src/
  api/         API client layer + response types (the only place that
               knows the backend contract)
  hooks/       useChiron — all session/message/run state
  components/  presentational + container components
  styles/      global.css design system
```

The backend contract is documented in `FRONTEND_AGENT_BRIEF.md` and is mirrored,
unchanged, in `src/api/`.
