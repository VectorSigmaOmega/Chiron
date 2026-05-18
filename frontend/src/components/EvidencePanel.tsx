/* ============================================================
   EvidencePanel — the right-side drawer. Full structured
   evidence behind an answer, examined on demand so the
   conversation itself stays uncluttered.
   ============================================================ */

import { useEffect, useRef, useState } from 'react'
import type { AssistantResponse, EvidenceItem } from '../api/types'
import { formatDate, formatStamp } from '../lib/format'
import { CloseIcon, ExternalIcon } from './icons'
import { Strength } from './Strength'

interface PanelProps {
  open: boolean
  response: AssistantResponse | null
  focusSourceId?: string | null
  onClose: () => void
}

export function EvidencePanel({
  open,
  response,
  focusSourceId,
  onClose,
}: PanelProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const [focused, setFocused] = useState<string | null>(null)

  // Escape closes the drawer
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // scroll to + briefly highlight a focused source
  useEffect(() => {
    if (!open || !focusSourceId) {
      setFocused(null)
      return
    }
    setFocused(focusSourceId)
    const esc =
      typeof CSS !== 'undefined' && CSS.escape
        ? CSS.escape(focusSourceId)
        : focusSourceId
    const scroll = window.setTimeout(() => {
      bodyRef.current
        ?.querySelector(`[data-src="${esc}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 130)
    const clear = window.setTimeout(() => setFocused(null), 2600)
    return () => {
      window.clearTimeout(scroll)
      window.clearTimeout(clear)
    }
  }, [open, focusSourceId])

  const items = response?.evidence_items ?? []

  return (
    <>
      <div
        className={open ? 'scrim scrim--open' : 'scrim'}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={open ? 'drawer drawer--open' : 'drawer'}
        aria-hidden={!open}
        aria-label="Evidence"
      >
        <div className="drawer__head">
          <div className="drawer__heading">
            <div className="drawer__title">Evidence</div>
            <div className="drawer__count">
              {items.length} item{items.length === 1 ? '' : 's'} examined
            </div>
          </div>
          <button
            type="button"
            className="drawer__close"
            onClick={onClose}
            aria-label="Close evidence"
          >
            <CloseIcon width={15} height={15} />
          </button>
        </div>

        <div className="drawer__body" ref={bodyRef}>
          {response?.last_literature_check_at && (
            <div className="drawer__checked">
              Literature checked{' '}
              {formatStamp(response.last_literature_check_at)}
            </div>
          )}

          {items.length === 0 ? (
            <p className="sessions__empty">
              No structured evidence accompanied this response.
            </p>
          ) : (
            items.map((ev, i) => (
              <EvidenceCard
                key={ev.evidence_id || ev.source_id || i}
                item={ev}
                index={i + 1}
                focused={!!focused && ev.source_id === focused}
              />
            ))
          )}
        </div>
      </aside>
    </>
  )
}

/* ---------- one evidence item ---------- */
function EvidenceCard({
  item,
  index,
  focused,
}: {
  item: EvidenceItem
  index: number
  focused: boolean
}) {
  const pico: Array<[string, string]> = (
    [
      ['Population', item.population],
      ['Intervention', item.intervention],
      ['Outcome', item.outcome],
    ] as Array<[string, string | null]>
  ).filter((row): row is [string, string] => !!row[1]?.trim())

  const srcMeta = [item.publisher, formatDate(item.publication_date)].filter(
    Boolean,
  )

  return (
    <article
      className={focused ? 'ev ev--focus' : 'ev'}
      data-src={item.source_id}
    >
      <div className="ev__top">
        <span className="ev__label">E{index}</span>
        <span className="ev__type">{item.source_type || 'source'}</span>
      </div>

      <div className="ev__claim">
        {item.key_claim?.trim() || 'No claim summary was provided.'}
      </div>
      {item.claim_type && (
        <div className="ev__claimtype">{item.claim_type}</div>
      )}

      <a
        className="ev__src"
        href={item.url || undefined}
        target="_blank"
        rel="noreferrer noopener"
      >
        <span className="ev__srctitle">
          {item.title || 'Untitled source'}
          <ExternalIcon
            width={12}
            height={12}
            style={{ flexShrink: 0, marginTop: 2 }}
          />
        </span>
        {srcMeta.length > 0 && (
          <span className="ev__srcmeta">{srcMeta.join('  ·  ')}</span>
        )}
      </a>

      {pico.length > 0 && (
        <div className="pico">
          {pico.map(([k, v]) => (
            <div className="pico__row" key={k}>
              <span className="pico__k">{k}</span>
              <span className="pico__v">{v}</span>
            </div>
          ))}
        </div>
      )}

      {item.applicability?.trim() && (
        <EvBlock head="Applicability" items={[item.applicability]} />
      )}
      {item.safety_notes.length > 0 && (
        <EvBlock head="Safety" items={item.safety_notes} variant="safety" />
      )}
      {item.limitations.length > 0 && (
        <EvBlock head="Limitations" items={item.limitations} />
      )}
      {item.uncertainty_notes.length > 0 && (
        <EvBlock head="Uncertainty" items={item.uncertainty_notes} />
      )}
      {item.supports_question_dimensions.length > 0 && (
        <EvBlock
          head="Addresses"
          items={[item.supports_question_dimensions.join('  ·  ')]}
        />
      )}

      {item.extracted_entities.length > 0 && (
        <div className="tags">
          {item.extracted_entities.map((t, i) => (
            <span className="tag" key={i}>
              {t}
            </span>
          ))}
        </div>
      )}

      <div className="drawer__strength">
        <Strength value={item.evidence_strength} />
      </div>
    </article>
  )
}

function EvBlock({
  head,
  items,
  variant,
}: {
  head: string
  items: string[]
  variant?: 'safety'
}) {
  return (
    <div className={variant === 'safety' ? 'evblock evblock--safety' : 'evblock'}>
      <div className="evblock__h">{head}</div>
      <ul className="evblock__list">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  )
}
