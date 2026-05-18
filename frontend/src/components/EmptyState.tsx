/* ============================================================
   EmptyState — shown for a fresh consultation with no messages.
   The Chiron mark draws itself in on load.
   ============================================================ */

import { ArrowUpRight, ChironMark } from './icons'

const EXAMPLES = [
  'What is the first-line treatment for newly diagnosed type 2 diabetes in adults?',
  'Is dual antiplatelet therapy indicated after a minor ischaemic stroke?',
  'Does vitamin D supplementation reduce fracture risk in older adults?',
]

export function EmptyState({
  onPick,
}: {
  onPick: (question: string) => void
}) {
  return (
    <div className="empty">
      <div className="empty__inner">
        <ChironMark className="empty__mark" draw />
        <h1 className="empty__title">
          What would you like to <em>know</em>?
        </h1>
        <p className="empty__body">
          Ask any clinical question. Chiron answers only from trusted,
          dated evidence — and tells you plainly when it cannot.
        </p>
        <div className="empty__examples">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              className="example"
              onClick={() => onPick(q)}
            >
              {q}
              <ArrowUpRight
                className="example__arrow"
                width={15}
                height={15}
              />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
