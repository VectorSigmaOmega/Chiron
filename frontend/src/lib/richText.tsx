/* ============================================================
   Minimal, safe rich-text rendering for assistant answers.
   Supports paragraphs, soft line breaks, **bold**, and inline
   [n] citation references that open the evidence drawer.
   No HTML is ever interpreted — text only.
   ============================================================ */

import { Fragment, type ReactNode } from 'react'

const CITE = /\[\s*(\d{1,3})\s*\]/g

function withCitations(
  text: string,
  keyPrefix: string,
  onCite?: (label: string) => void,
): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let i = 0
  let m: RegExpExecArray | null
  CITE.lastIndex = 0

  while ((m = CITE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const label = m[1]
    out.push(
      <span
        key={`${keyPrefix}-c${i++}`}
        className="cref"
        role="button"
        tabIndex={0}
        title={`Evidence ${label}`}
        onClick={() => onCite?.(label)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onCite?.(label)
          }
        }}
      >
        {label}
      </span>,
    )
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function inline(
  text: string,
  keyPrefix: string,
  onCite?: (label: string) => void,
): ReactNode[] {
  return text.split('**').map((seg, i) => {
    const key = `${keyPrefix}-s${i}`
    const body = withCitations(seg, key, onCite)
    return i % 2 === 1 ? (
      <strong key={key}>{body}</strong>
    ) : (
      <Fragment key={key}>{body}</Fragment>
    )
  })
}

/** Render an answer body into paragraphs of React nodes. */
export function renderRich(
  text: string,
  onCite?: (label: string) => void,
): ReactNode {
  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)

  const blocks = paragraphs.length ? paragraphs : [text]

  return blocks.map((para, p) => {
    const lines = para.split('\n')
    return (
      <p key={`p${p}`}>
        {lines.map((line, l) => (
          <Fragment key={`p${p}l${l}`}>
            {l > 0 && <br />}
            {inline(line, `p${p}l${l}`, onCite)}
          </Fragment>
        ))}
      </p>
    )
  })
}
