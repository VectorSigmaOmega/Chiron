/* Evidence-strength signal — one pill, four states. */

import type { EvidenceStrength } from '../api/types'

const KNOWN: EvidenceStrength[] = ['high', 'moderate', 'low', 'unknown']

const LABEL: Record<EvidenceStrength, string> = {
  high: 'Strong evidence',
  moderate: 'Moderate evidence',
  low: 'Limited evidence',
  unknown: 'Strength unknown',
}

export function Strength({
  value,
}: {
  value: string | null | undefined
}) {
  const v: EvidenceStrength =
    value && KNOWN.includes(value as EvidenceStrength)
      ? (value as EvidenceStrength)
      : 'unknown'

  return (
    <span className={`strength strength--${v}`}>
      <span className="strength__dot" />
      {LABEL[v]}
    </span>
  )
}
