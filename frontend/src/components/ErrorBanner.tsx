/* Recoverable error banner — message, optional retry, dismiss. */

import type { ChironError } from '../hooks/useChiron'
import { AlertIcon, CloseIcon } from './icons'

export function ErrorBanner({
  error,
  onDismiss,
}: {
  error: ChironError
  onDismiss: () => void
}) {
  return (
    <div className="banner" role="alert">
      <AlertIcon width={15} height={15} />
      <span className="banner__msg">{error.message}</span>
      {error.retry && (
        <button
          type="button"
          className="banner__act"
          onClick={() => {
            onDismiss()
            error.retry?.()
          }}
        >
          Try again
        </button>
      )}
      <button
        type="button"
        className="banner__close"
        onClick={onDismiss}
        aria-label="Dismiss"
      >
        <CloseIcon width={14} height={14} />
      </button>
    </div>
  )
}
