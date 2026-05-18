/* ============================================================
   Conversation — the centre pane: header, transcript, composer.
   Owns only the local draft; all server state comes via props.
   ============================================================ */

import { useEffect, useRef, useState } from 'react'
import type { AssistantResponse, Session } from '../api/types'
import type { ChatItem, ChironError, HealthState } from '../hooks/useChiron'
import { AssistantTurn } from './AssistantTurn'
import { Composer } from './Composer'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { ChironMark } from './icons'

interface ConversationProps {
  items: ChatItem[]
  activeSession: Session | null
  loadingMessages: boolean
  sending: boolean
  error: ChironError | null
  healthState: HealthState
  apiBaseUrl: string
  onSend: (text: string) => void
  onOpenEvidence: (
    response: AssistantResponse,
    focusSourceId?: string,
  ) => void
  onDismissError: () => void
  onRetryHealth: () => void
}

export function Conversation({
  items,
  activeSession,
  loadingMessages,
  sending,
  error,
  healthState,
  apiBaseUrl,
  onSend,
  onOpenEvidence,
  onDismissError,
  onRetryHealth,
}: ConversationProps) {
  const [draft, setDraft] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  const questionCount = items.filter((it) => it.kind === 'user').length
  const hasContent = items.length > 0

  // keep the latest turn in view
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [items])

  function handleSend() {
    const text = draft.trim()
    if (!text) return
    setDraft('')
    onSend(text)
  }

  return (
    <main className="pane">
      <header className="pane__head">
        <span className="pane__title">
          {activeSession?.title?.trim() || 'New consultation'}
        </span>
        <span className="pane__sub">
          {questionCount === 0
            ? 'Ready'
            : `${questionCount} question${questionCount === 1 ? '' : 's'}`}
        </span>
      </header>

      {error && <ErrorBanner error={error} onDismiss={onDismissError} />}

      <div className="scroll" ref={scrollRef}>
        {loadingMessages ? (
          <div className="empty">
            <div className="pending">
              <ChironMark className="pending__mark" draw />
              <span className="pending__text">Loading consultation…</span>
            </div>
          </div>
        ) : !hasContent ? (
          healthState === 'down' ? (
            <Offline apiBaseUrl={apiBaseUrl} onRetry={onRetryHealth} />
          ) : (
            <EmptyState onPick={(q) => onSend(q)} />
          )
        ) : (
          <div className="thread">
            {items.map((it, i) => (
              <div
                className="turn"
                key={it.key}
                style={{ animationDelay: `${Math.min(i, 6) * 0.05}s` }}
              >
                {renderItem(it, onOpenEvidence)}
              </div>
            ))}
          </div>
        )}
      </div>

      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={handleSend}
        sending={sending}
      />
    </main>
  )
}

function renderItem(
  it: ChatItem,
  onOpenEvidence: ConversationProps['onOpenEvidence'],
) {
  if (it.kind === 'user') {
    return (
      <div className="ask">
        <div className="role">Question</div>
        <div className="ask__body">{it.content}</div>
      </div>
    )
  }
  if (it.kind === 'pending') {
    return (
      <div className="reply">
        <div className="role">
          <ChironMark className="role__mark" />
          Chiron
        </div>
        <div className="pending">
          <ChironMark className="pending__mark" draw />
          <span className="pending__text">Consulting the evidence…</span>
        </div>
      </div>
    )
  }
  return (
    <AssistantTurn
      response={it.response}
      onOpenEvidence={(src) => onOpenEvidence(it.response, src)}
    />
  )
}

function Offline({
  apiBaseUrl,
  onRetry,
}: {
  apiBaseUrl: string
  onRetry: () => void
}) {
  return (
    <div className="empty">
      <div className="empty__inner">
        <ChironMark className="empty__mark" draw />
        <h1 className="empty__title">
          Can&rsquo;t reach the <em>backend</em>
        </h1>
        <p className="empty__body">
          Chiron has no connection to its evidence service. Start the
          backend, then retry — your consultations are safe.
        </p>
        <div className="offline">
          <div className="offline__title">No connection</div>
          <div className="offline__body">
            Expected to find the API at <code>{apiBaseUrl}</code>
          </div>
          <button
            type="button"
            className="offline__retry"
            onClick={onRetry}
          >
            Retry connection
          </button>
        </div>
      </div>
    </div>
  )
}
