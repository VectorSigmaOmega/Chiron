/* ============================================================
   App — composes the shell and owns evidence-drawer state.
   All server state lives in useChiron.
   ============================================================ */

import { useCallback, useState } from 'react'
import type { AssistantResponse } from './api/types'
import { Conversation } from './components/Conversation'
import { EvidencePanel } from './components/EvidencePanel'
import { Sidebar } from './components/Sidebar'
import { useChiron } from './hooks/useChiron'

interface EvidenceView {
  response: AssistantResponse
  focus: string | null
}

export default function App() {
  const chiron = useChiron()
  const [evidence, setEvidence] = useState<EvidenceView | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const openEvidence = useCallback(
    (response: AssistantResponse, focusSourceId?: string) => {
      setEvidence({ response, focus: focusSourceId ?? null })
      setDrawerOpen(true)
    },
    [],
  )

  const closeEvidence = useCallback(() => setDrawerOpen(false), [])

  const handleSelect = useCallback(
    (id: string) => {
      setDrawerOpen(false)
      void chiron.selectSession(id)
    },
    [chiron],
  )

  const handleNew = useCallback(() => {
    setDrawerOpen(false)
    chiron.newConsultation()
  }, [chiron])

  return (
    <div className="shell">
      <Sidebar
        sessions={chiron.sessions}
        activeId={chiron.activeId}
        loadingSessions={chiron.loadingSessions}
        healthState={chiron.healthState}
        health={chiron.health}
        onSelect={handleSelect}
        onNew={handleNew}
      />

      <Conversation
        items={chiron.items}
        activeSession={chiron.activeSession}
        loadingMessages={chiron.loadingMessages}
        sending={chiron.sending}
        error={chiron.error}
        healthState={chiron.healthState}
        apiBaseUrl={chiron.apiBaseUrl}
        onSend={chiron.send}
        onOpenEvidence={openEvidence}
        onDismissError={chiron.dismissError}
        onRetryHealth={chiron.checkHealth}
      />

      <EvidencePanel
        open={drawerOpen}
        response={evidence?.response ?? null}
        focusSourceId={drawerOpen ? evidence?.focus : null}
        onClose={closeEvidence}
      />
    </div>
  )
}
