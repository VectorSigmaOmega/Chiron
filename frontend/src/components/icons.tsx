/* ============================================================
   Icons — a small, consistent hand-drawn set.
   24×24 stroked grid, currentColor, no fills.
   The Chiron mark is the one exception: the signature line.
   ============================================================ */

import type { SVGProps } from 'react'

type P = SVGProps<SVGSVGElement>

function Stroke({ children, ...p }: P) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...p}
    >
      {children}
    </svg>
  )
}

/** The Chiron mark — one continuous looping line. The whole identity. */
export function ChironMark({
  draw = false,
  ...p
}: P & { draw?: boolean }) {
  return (
    <svg viewBox="0 0 64 32" fill="none" aria-hidden="true" {...p}>
      <path
        d="M32 16C32 5 18 5 18 16C18 27 32 27 32 16C32 5 46 5 46 16C46 27 32 27 32 16"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        pathLength={1}
        className={draw ? 'pending__draw' : undefined}
      />
    </svg>
  )
}

export const PlusIcon = (p: P) => (
  <Stroke {...p}>
    <path d="M12 5v14M5 12h14" />
  </Stroke>
)

export const SendIcon = (p: P) => (
  <Stroke {...p}>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </Stroke>
)

export const ArrowRight = (p: P) => (
  <Stroke {...p}>
    <path d="M4 12h14M12 6l6 6-6 6" />
  </Stroke>
)

export const ArrowUpRight = (p: P) => (
  <Stroke {...p}>
    <path d="M7 17 17 7M8 7h9v9" />
  </Stroke>
)

export const ExternalIcon = (p: P) => (
  <Stroke {...p}>
    <path d="M14 4h6v6M20 4l-8 8M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" />
  </Stroke>
)

export const CloseIcon = (p: P) => (
  <Stroke {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Stroke>
)

export const AlertIcon = (p: P) => (
  <Stroke {...p}>
    <path d="M12 4 2.5 20h19zM12 10v4M12 17.5h.01" />
  </Stroke>
)

export const ClarifyIcon = (p: P) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.4 9.4a2.6 2.6 0 1 1 3.4 2.5c-.8.3-.8 1-.8 1.6M12 16.6h.01" />
  </Stroke>
)

export const AbstainIcon = (p: P) => (
  <Stroke {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.2 12h7.6" />
  </Stroke>
)

export const SpinnerIcon = (p: P) => (
  <Stroke {...p}>
    <path d="M12 3a9 9 0 1 1-6.4 2.6" />
  </Stroke>
)
