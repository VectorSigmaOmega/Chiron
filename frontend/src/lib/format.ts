/* Small date/time formatters — warm, human, never ISO-raw in the UI. */

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

/** "12 May 2026" */
export function formatDate(iso: string | null | undefined): string {
  const d = parse(iso)
  if (!d) return iso ? String(iso) : ''
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

/** "just now" · "14m ago" · "3h ago" · "2d ago" · "12 May 2026" */
export function formatRelative(iso: string | null | undefined): string {
  const d = parse(iso)
  if (!d) return ''
  const min = Math.round((Date.now() - d.getTime()) / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.round(hr / 24)
  if (day < 7) return `${day}d ago`
  return formatDate(iso)
}

/** "12 May 2026 · 14:32" */
export function formatStamp(iso: string | null | undefined): string {
  const d = parse(iso)
  if (!d) return ''
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${formatDate(iso)} · ${hh}:${mm}`
}
