/* ============================================================
   Composer — the question input. Auto-growing, keyboard-first.
   ============================================================ */

import { useEffect, useRef } from 'react'
import { SendIcon, SpinnerIcon } from './icons'

interface ComposerProps {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  sending: boolean
}

export function Composer({
  value,
  onChange,
  onSubmit,
  sending,
}: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

  // grow the textarea with its content, up to a ceiling
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`
  }, [value])

  const canSend = value.trim().length > 0 && !sending

  function submit() {
    if (canSend) onSubmit()
  }

  return (
    <div className="composer">
      <div className="composer__inner">
        <div className="composer__field">
          <textarea
            ref={ref}
            rows={1}
            value={value}
            placeholder="Ask a clinical question…"
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
          />
          <button
            type="button"
            className="send"
            disabled={!canSend}
            onClick={submit}
            aria-label="Send question"
          >
            {sending ? (
              <SpinnerIcon className="spin" width={17} height={17} />
            ) : (
              <SendIcon width={17} height={17} />
            )}
          </button>
        </div>
        <div className="composer__hint">
          <span>Chiron answers only from cited evidence.</span>
          <span>
            <kbd>↵</kbd> send&nbsp;&nbsp;<kbd>⇧ ↵</kbd> new line
          </span>
        </div>
      </div>
    </div>
  )
}
