import { useEffect, useRef } from "react";
import type { ChatMessage, ChatSession, Citation } from "@/lib/types";
import { MessageRouter } from "./MessageBlocks";
import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { ConversationHeader } from "./ConversationHeader";

interface ConversationPaneProps {
  session: ChatSession | null;
  pendingMessage: ChatMessage | null;
  activeCitation: string | null;
  evidenceOpen: boolean;
  onSubmit: (content: string) => void;
  onCitationActivate: (label: string | null) => void;
  onSelectCitation: (c: Citation) => void;
  onPickClarification: (option: string) => void;
  onRetry: () => void;
  onToggleEvidence: () => void;
  isThinking: boolean;
  isLoadingSession: boolean;
}

export function ConversationPane({
  session,
  pendingMessage,
  activeCitation,
  evidenceOpen,
  onSubmit,
  onCitationActivate,
  onSelectCitation,
  onPickClarification,
  onRetry,
  onToggleEvidence,
  isThinking,
  isLoadingSession,
}: ConversationPaneProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const messages = session?.messages ?? [];
  const allMessages = pendingMessage ? [...messages, pendingMessage] : messages;
  const lastAssistantWithEvidence = [...messages]
    .reverse()
    .find((m) => m.kind === "assistant" && m.response.evidence_items.length > 0);
  const sourceCount =
    lastAssistantWithEvidence && lastAssistantWithEvidence.kind === "assistant"
      ? lastAssistantWithEvidence.response.evidence_items.length
      : 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [allMessages.length, pendingMessage]);

  const empty = !session || messages.length === 0;

  return (
    <main className="relative flex h-full min-w-0 flex-1 flex-col bg-ink">
      {!empty && (
        <ConversationHeader
          session={session!}
          evidenceOpen={evidenceOpen}
          onToggleEvidence={onToggleEvidence}
          hasEvidence={!!lastAssistantWithEvidence}
          sourceCount={sourceCount}
        />
      )}

      <div className="flex-1 overflow-y-auto">
        {isLoadingSession ? (
          <div className="mx-auto flex h-full w-full max-w-[720px] items-center px-10 py-10">
            <div className="space-y-3">
              <div className="ui-label text-bone-deep">loading consult</div>
              <p
                className="font-serif text-[16px] italic leading-[1.5] text-bone-mute"
                style={{ fontVariationSettings: '"opsz" 16' }}
              >
                Rehydrating conversation state from the backend.
              </p>
            </div>
          </div>
        ) : empty ? (
          <EmptyState onPick={onSubmit} />
        ) : (
          <div className="mx-auto w-full max-w-[720px] px-10 py-10">
            <div className="flex flex-col gap-12">
              {allMessages.map((message) => (
                <MessageRouter
                  key={message.id}
                  message={message}
                  activeCitation={activeCitation}
                  onCitationActivate={onCitationActivate}
                  onSelectCitation={onSelectCitation}
                  onPickClarification={onPickClarification}
                  onRetry={onRetry}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
        )}
      </div>

      <div className="px-10 pb-8 pt-3">
        <div className="mx-auto w-full max-w-[720px]">
          <Composer
            onSubmit={onSubmit}
            disabled={isThinking}
            autoFocus={empty}
            placeholder={
              isThinking
                ? "working…"
                : empty
                  ? "ask anything in medicine"
                  : "continue"
            }
          />
        </div>
      </div>
    </main>
  );
}
