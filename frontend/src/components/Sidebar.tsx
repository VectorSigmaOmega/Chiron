/* ============================================================
   Sidebar — identity, new-consultation action, session list,
   and the backend health footer.
   ============================================================ */

import type { Health } from '../api/types'
import type { HealthState } from '../hooks/useChiron'
import type { Session } from '../api/types'
import { formatRelative } from '../lib/format'
import { ChironMark, PlusIcon } from './icons'

interface SidebarProps {
  sessions: Session[]
  activeId: string | null
  loadingSessions: boolean
  healthState: HealthState
  health: Health | null
  onSelect: (id: string) => void
  onNew: () => void
}

export function Sidebar({
  sessions,
  activeId,
  loadingSessions,
  healthState,
  health,
  onSelect,
  onNew,
}: SidebarProps) {
  return (
    <aside className="rail">
      <div className="rail__head">
        <div className="brand">
          <ChironMark className="brand__mark" />
          <span className="brand__name">Chiron</span>
        </div>
        <p className="brand__tag">
          Grounded answers from cited evidence — or a clear, honest
          abstention.
        </p>
      </div>

      <button className="rail__new" onClick={onNew} type="button">
        <PlusIcon width={15} height={15} />
        New consultation
      </button>

      <div className="rail__label">Consultations</div>

      <nav className="sessions" aria-label="Past consultations">
        {loadingSessions && sessions.length === 0 ? (
          <p className="sessions__empty">Loading…</p>
        ) : sessions.length === 0 ? (
          <p className="sessions__empty">No consultations yet.</p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              className={
                s.id === activeId ? 'session session--active' : 'session'
              }
              onClick={() => onSelect(s.id)}
              aria-current={s.id === activeId ? 'true' : undefined}
            >
              <span className="session__title">
                {s.title?.trim() || 'Untitled consultation'}
              </span>
              <span className="session__meta">
                {formatRelative(s.updated_at || s.created_at)}
              </span>
            </button>
          ))
        )}
      </nav>

      <HealthIndicator state={healthState} health={health} />
    </aside>
  )
}

function HealthIndicator({
  state,
  health,
}: {
  state: HealthState
  health: Health | null
}) {
  const label =
    state === 'checking'
      ? 'Checking backend…'
      : state === 'ok'
        ? 'Backend online'
        : 'Backend offline'

  const dotClass =
    state === 'ok'
      ? 'health__dot--ok'
      : state === 'down'
        ? 'health__dot--down'
        : ''

  return (
    <div className="health">
      <span className={`health__dot ${dotClass}`} />
      <span>{label}</span>
      {state === 'ok' && health?.llm_mode && (
        <span className="health__mode">{health.llm_mode}</span>
      )}
    </div>
  )
}
