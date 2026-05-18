/* ============================================================
   Chiron API client — the single integration boundary.
   Every backend route the app uses lives here, and only here.
   ============================================================ */

import type {
  BackendMessage,
  Health,
  RunStep,
  SendMessageResult,
  Session,
} from './types'

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'
).replace(/\/+$/, '')

/** A network/HTTP failure surfaced to the UI in a recoverable way. */
export class ApiError extends Error {
  readonly status: number
  /** true when the request never reached the server (server down, CORS, DNS) */
  readonly offline: boolean

  constructor(message: string, status = 0, offline = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.offline = offline
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = opts

  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    if (signal?.aborted) throw err
    throw new ApiError(
      'Could not reach the Chiron backend.',
      0,
      true,
    )
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const data = await res.json()
      if (data && typeof data.detail === 'string') detail = data.detail
    } catch {
      /* response had no JSON body — keep the generic message */
    }
    throw new ApiError(detail, res.status, false)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  baseUrl: BASE_URL,

  /** Connectivity + LLM-mode probe. */
  health: (signal?: AbortSignal) => request<Health>('/health', { signal }),

  /** All sessions, newest expected first (left as backend returns). */
  listSessions: (signal?: AbortSignal) =>
    request<Session[]>('/sessions', { signal }),

  /** Create a session. Title may be null. */
  createSession: (title: string | null, signal?: AbortSignal) =>
    request<Session>('/sessions', { method: 'POST', body: { title }, signal }),

  /** All stored messages for a session. */
  listMessages: (sessionId: string, signal?: AbortSignal) =>
    request<BackendMessage[]>(`/sessions/${sessionId}/messages`, { signal }),

  /** Submit a user message and trigger a backend run. */
  sendMessage: (sessionId: string, content: string, signal?: AbortSignal) =>
    request<SendMessageResult>(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: { role: 'user', content },
      signal,
    }),

  /** Run steps — optional, used for the debug/progress view. */
  listRunSteps: (runId: string, signal?: AbortSignal) =>
    request<RunStep[]>(`/runs/${runId}/steps`, { signal }),
}
