import { motion } from "framer-motion";
import { Wordmark } from "./Mark";
import type { ChatSession } from "@/lib/types";

interface SidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const minutes = Math.floor((now - then) / 60_000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
}: SidebarProps) {
  return (
    <aside className="relative flex h-full w-[240px] shrink-0 flex-col bg-ink-deep">
      <div className="absolute inset-y-0 right-0 w-px bg-ink-rule" />

      <div className="px-6 pt-7 pb-8">
        <Wordmark size="md" />
      </div>

      <button
        onClick={onNewSession}
        className="group mx-6 mb-8 flex items-center gap-2 text-left font-mono text-[11.5px] tracking-wide text-bone-soft transition-colors duration-200 hover:text-ember"
      >
        <span className="text-ember opacity-70 group-hover:opacity-100 transition-opacity">
          +
        </span>
        <span>new consult</span>
        <span className="ml-auto text-[10px] text-bone-deep">⌘N</span>
      </button>

      <nav className="flex-1 overflow-y-auto px-2 pb-8">
        {sessions.map((session, i) => (
          <SessionItem
            key={session.id}
            session={session}
            active={session.id === activeSessionId}
            onSelect={onSelectSession}
            delay={i * 0.04}
          />
        ))}
      </nav>
    </aside>
  );
}

function SessionItem({
  session,
  active,
  onSelect,
  delay,
}: {
  session: ChatSession;
  active: boolean;
  onSelect: (id: string) => void;
  delay: number;
}) {
  return (
    <motion.button
      onClick={() => onSelect(session.id)}
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        delay,
        duration: 0.5,
        ease: [0.22, 1, 0.36, 1],
      }}
      className="group relative block w-full px-4 py-2 text-left"
    >
      {active && (
        <motion.span
          layoutId="active-session"
          className="absolute left-0 top-1/2 h-[14px] w-[2px] -translate-y-1/2 bg-ember"
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          style={{
            boxShadow: "0 0 8px oklch(0.78 0.155 72 / 0.8)",
          }}
        />
      )}
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={`truncate font-serif text-[14px] leading-tight transition-colors duration-200 ${
            active
              ? "text-bone"
              : "text-bone-soft group-hover:text-bone"
          }`}
          style={{ fontVariationSettings: '"opsz" 14' }}
        >
          {session.title}
        </span>
        <span className="shrink-0 font-mono text-[10px] tabular-nums text-bone-deep">
          {formatRelative(session.created_at)}
        </span>
      </div>
    </motion.button>
  );
}
