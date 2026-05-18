/* ============================================================
   AssistantTurn — renders one assistant response in whichever
   of the three contractual states it arrived in.
   ============================================================ */

import type { AssistantResponse, Citation } from '../api/types'
import { formatDate } from '../lib/format'
import { renderRich } from '../lib/richText'
import {
  AbstainIcon,
  ArrowRight,
  ChironMark,
  ClarifyIcon,
  ExternalIcon,
} from './icons'
import { Strength } from './Strength'

interface TurnProps {
  response: AssistantResponse
  /** open the evidence drawer; pass a source id to focus a card */
  onOpenEvidence: (focusSourceId?: string) => void
}

/** map an inline [n] reference back to a source id, if we can */
function sourceForLabel(
  citations: Citation[],
  label: string,
): string | undefined {
  const want = label.replace(/\D/g, '')
  const byLabel = citations.find(
    (c) => (c.label || '').replace(/\D/g, '') === want,
  )
  if (byLabel) return byLabel.source_id
  const idx = Number(want) - 1
  return idx >= 0 && idx < citations.length
    ? citations[idx].source_id
    : undefined
}

export function AssistantTurn({ response, onOpenEvidence }: TurnProps) {
  return (
    <div className="reply">
      <div className="role">
        <ChironMark className="role__mark" />
        Chiron
      </div>
      {response.status === 'needs_clarification' ? (
        <ClarificationView response={response} />
      ) : response.status === 'abstained' ? (
        <AbstentionView response={response} />
      ) : (
        <AnsweredView response={response} onOpenEvidence={onOpenEvidence} />
      )}
    </div>
  )
}

/* ---------- answered ---------- */
function AnsweredView({ response, onOpenEvidence }: TurnProps) {
  const { answer, evidence_summary, citations, evidence_items, limitations } =
    response

  const body =
    answer?.trim() ||
    (evidence_summary.length ? evidence_summary.join('\n\n') : '')

  const handleCite = (label: string) =>
    onOpenEvidence(sourceForLabel(citations, label))

  return (
    <>
      <div className="answer">
        {body ? (
          renderRich(body, handleCite)
        ) : (
          <p style={{ color: 'var(--ink-faint)', fontStyle: 'italic' }}>
            No answer text was returned for this question.
          </p>
        )}
      </div>

      <div className="metastrip">
        <Strength value={response.evidence_strength} />
        {evidence_items.length > 0 && (
          <button
            type="button"
            className="examine"
            onClick={() => onOpenEvidence()}
          >
            Examine evidence · {evidence_items.length}
            <ArrowRight width={14} height={14} />
          </button>
        )}
      </div>

      {citations.length > 0 && (
        <CitationList citations={citations} />
      )}

      {limitations.length > 0 && (
        <Limitations items={limitations} />
      )}
    </>
  )
}

/* ---------- needs clarification ---------- */
function ClarificationView({ response }: { response: AssistantResponse }) {
  return (
    <div className="card card--clarify">
      <div className="card__tag">
        <ClarifyIcon width={13} height={13} />
        Needs clarification
      </div>
      <div className="card__q">
        {response.clarification_question?.trim() ||
          'Could you add a little more detail to your question?'}
      </div>
      <p className="card__hint">
        Reply below to continue — Chiron will use your answer to narrow
        the evidence search.
      </p>
    </div>
  )
}

/* ---------- abstained ---------- */
function AbstentionView({ response }: { response: AssistantResponse }) {
  return (
    <div className="card card--abstain">
      <div className="card__tag">
        <AbstainIcon width={13} height={13} />
        Abstained — no safe answer
      </div>
      {response.abstention_class && (
        <span className="card__class">{response.abstention_class}</span>
      )}
      <p className="card__reason">
        {response.abstention_reason?.trim() ||
          'Chiron could not assemble trusted evidence sufficient to answer this safely.'}
      </p>
      {response.limitations.length > 0 && (
        <Limitations items={response.limitations} />
      )}
    </div>
  )
}

/* ---------- shared: limitations ---------- */
function Limitations({ items }: { items: string[] }) {
  return (
    <div className="limits">
      <div className="limits__head">Limitations</div>
      <ul className="limits__list">
        {items.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </div>
  )
}

/* ---------- shared: citations ---------- */
function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <div className="cites">
      <div className="cites__head">
        {citations.length} source{citations.length === 1 ? '' : 's'}
      </div>
      {citations.map((c, i) => {
        const meta = [
          c.publisher,
          c.source_type,
          formatDate(c.publication_date),
        ].filter(Boolean)
        return (
          <a
            key={c.source_id || i}
            className="cite"
            href={c.url || undefined}
            target="_blank"
            rel="noreferrer noopener"
          >
            <span className="cite__num">
              {(c.label || '').replace(/\D/g, '') || i + 1}
            </span>
            <span className="cite__body">
              <span className="cite__title">
                {c.title || 'Untitled source'}
              </span>
              {meta.length > 0 && (
                <span className="cite__meta">
                  {meta.map((m, mi) => (
                    <span key={mi}>{m}</span>
                  ))}
                </span>
              )}
            </span>
            <ExternalIcon className="cite__ext" width={13} height={13} />
          </a>
        )
      })}
    </div>
  )
}
