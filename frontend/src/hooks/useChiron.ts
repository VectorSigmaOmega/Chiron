/* ============================================================
   useChiron — the whole client-side state machine.
   Sessions, the active thread, health, sending, error recovery.
   Components stay presentational; this hook owns the contract.
   ============================================================ */

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type {
  AssistantResponse,
  AssistantStatus,
  BackendMessage,
  Health,
  RunProgressEvent,
  Session,
} from '../api/types'

/* ---- rendered conversation items ---- */
export type ChatItem =
  | { kind: 'user'; key: string; content: string; createdAt: string }
  | {
      kind: 'assistant'
      key: string
      response: AssistantResponse
      createdAt: string
    }
  | { kind: 'pending'; key: string; runId?: string; progress: string[] }

export type HealthState = 'checking' | 'ok' | 'down'

export interface ChironError {
  scope: 'sessions' | 'messages' | 'send'
  message: string
  retry?: () => void
}

/* ---- helpers ---- */
const STATUSES: AssistantStatus[] = [
  'answered',
  'needs_clarification',
  'abstained',
]

function uid(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2)
}

function arr<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : []
}

function errMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return 'Something went wrong.'
}

function deriveTitle(text: string): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (clean.length <= 52) return clean
  const cut = clean.slice(0, 52)
  const lastSpace = cut.lastIndexOf(' ')
  return (lastSpace > 24 ? cut.slice(0, lastSpace) : cut).trimEnd() + '…'
}

function appendProgress(progress: string[], message: string): string[] {
  if (!message) return progress
  if (progress[progress.length - 1] === message) return progress
  return [...progress, message].slice(-6)
}

function isResponseShape(v: unknown): boolean {
  return (
    !!v &&
    typeof v === 'object' &&
    typeof (v as Record<string, unknown>).status === 'string'
  )
}

/** Coerce arbitrary metadata into a safe, fully-populated response object. */
function normalizeResponse(
  raw: Record<string, unknown>,
  fallbackText: string,
): AssistantResponse {
  const status = STATUSES.includes(raw.status as AssistantStatus)
    ? (raw.status as AssistantStatus)
    : 'answered'
  return {
    status,
    answer: (raw.answer as string | null) ?? null,
    clarification_question:
      (raw.clarification_question as string | null) ?? null,
    abstention_class: (raw.abstention_class as string | null) ?? null,
    abstention_reason: (raw.abstention_reason as string | null) ?? null,
    evidence_summary: arr(raw.evidence_summary),
    evidence_strength: (raw.evidence_strength as any) ?? null,
    limitations: arr(raw.limitations),
    citations: arr(raw.citations),
    evidence_items: arr(raw.evidence_items),
    last_literature_check_at:
      (raw.last_literature_check_at as string | null) ?? null,
    run_id: raw.run_id as string | undefined,
  }
}

/** Turn a stored assistant message into a renderable response. */
function toAssistantResponse(m: BackendMessage): AssistantResponse {
  const meta = (m.metadata_json ?? {}) as Record<string, unknown>
  if (isResponseShape(meta)) return normalizeResponse(meta, m.content)
  if (isResponseShape(meta.response)) {
    return normalizeResponse(
      { ...(meta.response as Record<string, unknown>), run_id: meta.run_id },
      m.content,
    )
  }
  // No structured payload — fall back to the readable text content.
  return normalizeResponse({ status: 'answered', answer: m.content }, m.content)
}

function toItem(m: BackendMessage): ChatItem {
  if (m.role === 'user') {
    return {
      kind: 'user',
      key: m.id,
      content: m.content,
      createdAt: m.created_at,
    }
  }
  const response = toAssistantResponse(m)
  return {
    kind: 'assistant',
    key: response.run_id || m.id,
    response,
    createdAt: m.created_at,
  }
}

/* ============================================================ */
export function useChiron() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [items, setItems] = useState<ChatItem[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [healthState, setHealthState] = useState<HealthState>('checking')
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<ChironError | null>(null)

  const sendingRef = useRef(false)
  const streamCleanupRef = useRef<null | (() => void)>(null)

  /* ---- health ---- */
  const checkHealth = useCallback(async () => {
    try {
      const h = await api.health()
      setHealth(h)
      setHealthState('ok')
    } catch {
      setHealth(null)
      setHealthState('down')
    }
  }, [])

  /* ---- sessions ---- */
  const loadSessions = useCallback(async () => {
    setLoadingSessions(true)
    try {
      const list = await api.listSessions()
      setSessions(list)
      setError((e) => (e?.scope === 'sessions' ? null : e))
    } catch (err) {
      setError({
        scope: 'sessions',
        message: errMessage(err),
        retry: loadSessions,
      })
    } finally {
      setLoadingSessions(false)
    }
  }, [])

  /* ---- select an existing session ---- */
  const selectSession = useCallback(
    async (id: string) => {
      setActiveId(id)
      setItems([])
      setLoadingMessages(true)
      setError((e) => (e?.scope === 'sessions' ? e : null))
      try {
        const msgs = await api.listMessages(id)
        setItems(msgs.map(toItem))
      } catch (err) {
        setError({
          scope: 'messages',
          message: errMessage(err),
          retry: () => selectSession(id),
        })
      } finally {
        setLoadingMessages(false)
      }
    },
    [],
  )

  /* ---- start a fresh consultation (session created lazily on send) ---- */
  const newConsultation = useCallback(() => {
    setActiveId(null)
    setItems([])
    setError(null)
  }, [])

  /* ---- submit a question ---- */
  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim()
      if (!text || sendingRef.current) return

      sendingRef.current = true
      setSending(true)
      setError(null)

      const userKey = uid()
      const pendingKey = uid()
      setItems((prev) => [
        ...prev,
        {
          kind: 'user',
          key: userKey,
          content: text,
          createdAt: new Date().toISOString(),
        },
        {
          kind: 'pending',
          key: pendingKey,
          progress: ['Starting consultation…'],
        },
      ])

      let sessionId = activeId
      try {
        if (!sessionId) {
          const created = await api.createSession(deriveTitle(text))
          sessionId = created.id
          setSessions((prev) => [created, ...prev])
          setActiveId(created.id)
        }

        const result = await api.sendMessage(sessionId, text)
        setItems((prev) =>
          prev.map((it) =>
            it.key === pendingKey
              ? {
                  ...it,
                  kind: 'pending',
                  runId: result.run_id,
                  progress: appendProgress(
                    it.kind === 'pending' ? it.progress : [],
                    'Connecting to live run updates…',
                  ),
                }
              : it,
          ),
        )

        streamCleanupRef.current?.()
        streamCleanupRef.current = api.streamRunEvents(result.run_id, {
          onProgress: (event: RunProgressEvent) => {
            setItems((prev) =>
              prev.map((it) =>
                it.key === pendingKey && it.kind === 'pending'
                  ? {
                      ...it,
                      runId: result.run_id,
                      progress: appendProgress(
                        it.progress,
                        event.message || 'Consulting the evidence…',
                      ),
                    }
                  : it,
              ),
            )
          },
          onFinal: (event: RunProgressEvent) => {
            const response = normalizeResponse(
              (event.response as unknown as Record<string, unknown>) || {},
              text,
            )
            setItems((prev) =>
              prev.map((it) =>
                it.key === pendingKey
                  ? {
                      kind: 'assistant',
                      key: response.run_id || result.run_id || pendingKey,
                      response,
                      createdAt: new Date().toISOString(),
                    }
                  : it,
              ),
            )
            api.listSessions().then(setSessions).catch(() => {})
            streamCleanupRef.current = null
            sendingRef.current = false
            setSending(false)
          },
          onError: async (event: RunProgressEvent) => {
            try {
              const run = await api.getRun(result.run_id)
              const finalRaw = (run.final_response_json ?? {}) as Record<string, unknown>
              if (run.status === 'completed' && finalRaw.status) {
                const response = normalizeResponse(
                  { ...finalRaw, run_id: result.run_id },
                  text,
                )
                setItems((prev) =>
                  prev.map((it) =>
                    it.key === pendingKey
                      ? {
                          kind: 'assistant',
                          key: response.run_id || result.run_id || pendingKey,
                          response,
                          createdAt: new Date().toISOString(),
                        }
                      : it,
                  ),
                )
                api.listSessions().then(setSessions).catch(() => {})
                return
              }
            } catch {
              /* fall through to user-facing error */
            }

            setItems((prev) => prev.filter((it) => it.key !== pendingKey))
            setError({
              scope: 'send',
              message: event.message || 'Consultation stream failed.',
              retry: () => {
                setItems((prev) => prev.filter((it) => it.key !== userKey))
                void send(text)
              },
            })
            streamCleanupRef.current = null
            sendingRef.current = false
            setSending(false)
          },
        })
      } catch (err) {
        setItems((prev) => prev.filter((it) => it.key !== pendingKey))
        setError({
          scope: 'send',
          message: errMessage(err),
          retry: () => {
            setItems((prev) => prev.filter((it) => it.key !== userKey))
            void send(text)
          },
        })
      }
    },
    [activeId],
  )

  const dismissError = useCallback(() => setError(null), [])

  /* ---- mount: load sessions + probe health, then poll health ---- */
  useEffect(() => {
    void loadSessions()
    void checkHealth()
    const t = window.setInterval(checkHealth, 45_000)
    return () => {
      window.clearInterval(t)
      streamCleanupRef.current?.()
    }
  }, [loadSessions, checkHealth])

  const activeSession = sessions.find((s) => s.id === activeId) ?? null

  return {
    sessions,
    activeId,
    activeSession,
    items,
    health,
    healthState,
    loadingSessions,
    loadingMessages,
    sending,
    error,
    apiBaseUrl: api.baseUrl,
    send,
    selectSession,
    newConsultation,
    checkHealth,
    dismissError,
  }
}
