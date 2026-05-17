import { motion } from "framer-motion";
import type { ChatSession } from "@/lib/types";

interface ConversationHeaderProps {
  session: ChatSession;
  evidenceOpen: boolean;
  onToggleEvidence: () => void;
  hasEvidence: boolean;
  sourceCount: number;
}

export function ConversationHeader({
  session,
  evidenceOpen,
  onToggleEvidence,
  hasEvidence,
  sourceCount,
}: ConversationHeaderProps) {
  return (
    <header className="relative flex h-16 shrink-0 items-end px-10 pb-3">
      <motion.h2
        key={session.id}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="flex-1 truncate font-serif text-[17px] italic leading-tight text-bone"
        style={{ fontVariationSettings: '"opsz" 17' }}
      >
        {session.title}
      </motion.h2>
      {hasEvidence && (
        <button
          onClick={onToggleEvidence}
          className="group flex items-baseline gap-1.5 font-mono text-[11px] tracking-wide text-bone-mute transition-colors duration-200 hover:text-ember"
        >
          <span>{evidenceOpen ? "hide" : "view"}</span>
          <span className="text-bone-deep group-hover:text-ember transition-colors duration-200">
            evidence
          </span>
          <span className="text-ember">·</span>
          <span className="tabular-nums text-bone-soft">{sourceCount}</span>
        </button>
      )}
    </header>
  );
}
