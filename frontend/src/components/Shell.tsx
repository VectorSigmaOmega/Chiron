import { useEffect, useMemo, useState } from "react";
import type {
  AssistantMessage,
  ChatMessage,
  ChatSession,
  Citation,
  PendingMessage,
  TraceStep,
} from "@/lib/types";
import {
  buildErrorMessage,
  buildPendingMessage,
  chatClient,
  withSessionMessages,
} from "@/lib/api";
import { Sidebar } from "./Sidebar";
import { ConversationPane } from "./ConversationPane";
import { EvidencePanel } from "./EvidencePanel";

function id(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function Shell() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<PendingMessage | null>(
    null,
  );
  const [activeCitation, setActiveCitation] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);

  useEffect(() => {
    chatClient.listSessions().then((s) => {
      setSessions(s);
      if (s.length > 0) setActiveSessionId(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (!activeSessionId) return;
    const session = sessions.find((item) => item.id === activeSessionId);
    if (!session || session.messagesLoaded) return;

    let cancelled = false;
    setLoadingSessionId(activeSessionId);
    chatClient
      .listMessages(activeSessionId)
      .then((messages) => {
        if (cancelled) return;
        setSessions((curr) =>
          curr.map((item) =>
            item.id === activeSessionId ? withSessionMessages(item, messages) : item,
          ),
        );
      })
      .catch((error) => {
        if (cancelled) return;
        setSessions((curr) =>
          curr.map((item) =>
            item.id === activeSessionId
              ? withSessionMessages(
                  item,
                  [
                    buildErrorMessage(
                      error instanceof Error
                        ? error.message
                        : "Failed to load the conversation from the backend.",
                    ),
                  ],
                )
              : item,
          ),
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingSessionId((current) => (current === activeSessionId ? null : current));
      });

    return () => {
      cancelled = true;
    };
  }, [activeSessionId, sessions]);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) ?? null;

  // The assistant message whose evidence the panel should reflect.
  const activeEvidenceMessage: AssistantMessage | null = useMemo(() => {
    if (!activeSession) return null;
    const messages = activeSession.messages;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.kind === "assistant" && m.response.evidence_items.length > 0) {
        return m;
      }
    }
    return null;
  }, [activeSession]);

  function patchSession(updater: (s: ChatSession) => ChatSession) {
    if (!activeSessionId) return;
    setSessions((curr) =>
      curr.map((s) => (s.id === activeSessionId ? updater(s) : s)),
    );
  }

  function appendMessage(msg: ChatMessage) {
    patchSession((s) => ({
      ...s,
      messages: [...s.messages, msg],
      preview: msg.kind === "user" ? msg.content : s.preview,
    }));
  }

  async function handleSubmit(content: string) {
    setActiveCitation(null);

    // If no session is selected, create one.
    let sessionId = activeSessionId;
    if (!sessionId || !activeSession) {
      const created = await chatClient.createSession(content);
      setSessions((curr) => [created, ...curr]);
      sessionId = created.id;
      setActiveSessionId(created.id);
    }

    const userMsg: ChatMessage = {
      id: id("msg"),
      kind: "user",
      content,
      created_at: new Date().toISOString(),
    };

    setSessions((curr) =>
      curr.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              title:
                s.messages.length === 0
                  ? content.slice(0, 64).replace(/\s+/g, " ").trim() +
                    (content.length > 64 ? "…" : "")
                  : s.title,
              preview: content,
              messages: [...s.messages, userMsg],
            }
          : s,
      ),
    );

    setThinking(true);
    const pending: PendingMessage = buildPendingMessage();
    setPendingMessage(pending);

    try {
      const result = await chatClient.sendMessage(
        sessionId!,
        content,
        (steps: TraceStep[]) => {
          setPendingMessage((prev) =>
            prev ? { ...prev, trace: steps } : prev,
          );
        },
      );
      const assistantMsg: AssistantMessage = {
        id: id("msg"),
        kind: "assistant",
        run_id: result.run_id,
        created_at: new Date().toISOString(),
        response: result.response,
      };
      setPendingMessage(null);
      setSessions((curr) =>
        curr.map((s) =>
          s.id === sessionId
            ? { ...s, messages: [...s.messages, assistantMsg] }
            : s,
        ),
      );
      if (
        result.response.evidence_items.length > 0 &&
        !evidenceOpen &&
        window.innerWidth > 1280
      ) {
        setEvidenceOpen(true);
      }
    } catch (e) {
      setPendingMessage(null);
      appendMessage(
        buildErrorMessage(
          e instanceof Error ? e.message : "Backend connection failed.",
        ),
      );
    } finally {
      setThinking(false);
    }
  }

  function handleNewSession() {
    setActiveSessionId(null);
    setPendingMessage(null);
    setActiveCitation(null);
  }

  function handleRetry() {
    if (!activeSession) return;
    // Find last user message
    const messages = activeSession.messages;
    let lastUser = "";
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].kind === "user") {
        lastUser = (messages[i] as ChatMessage & { content: string }).content;
        break;
      }
    }
    // Strip trailing error message
    patchSession((s) => ({
      ...s,
      messages: s.messages.filter((m) => m.kind !== "error"),
    }));
    if (lastUser) handleSubmit(lastUser);
  }

  function handlePickClarification(option: string) {
    handleSubmit(option);
  }

  function handleSelectCitation(c: Citation) {
    setActiveCitation(c.label);
    setEvidenceOpen(true);
  }

  return (
    <div className="flex h-full w-full">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={(id) => {
          setActiveSessionId(id);
          setActiveCitation(null);
          setPendingMessage(null);
        }}
        onNewSession={handleNewSession}
      />
      <ConversationPane
        session={activeSession}
        pendingMessage={pendingMessage}
        activeCitation={activeCitation}
        evidenceOpen={evidenceOpen}
        onSubmit={handleSubmit}
        onCitationActivate={setActiveCitation}
        onSelectCitation={handleSelectCitation}
        onPickClarification={handlePickClarification}
        onRetry={handleRetry}
        onToggleEvidence={() => setEvidenceOpen((v) => !v)}
        isThinking={thinking}
        isLoadingSession={loadingSessionId === activeSessionId}
      />
      <EvidencePanel
        message={activeEvidenceMessage}
        activeCitation={activeCitation}
        open={evidenceOpen && !!activeEvidenceMessage}
        onClose={() => setEvidenceOpen(false)}
        onCitationActivate={setActiveCitation}
      />
    </div>
  );
}
