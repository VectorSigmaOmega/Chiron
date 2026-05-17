import { Fragment } from "react";
import { motion } from "framer-motion";
import type { Citation } from "@/lib/types";

interface AnswerProseProps {
  text: string;
  citations: Citation[];
  activeCitation: string | null;
  onCitationActivate: (label: string | null) => void;
  staggered?: boolean;
}

type Token =
  | { kind: "text"; value: string }
  | { kind: "bold"; value: string }
  | { kind: "cite"; label: string };

function tokenize(line: string): Token[] {
  const tokens: Token[] = [];
  const re = /\*\*([^*]+)\*\*|\[(\d+)\]/g;
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    if (m.index > lastIndex) {
      tokens.push({ kind: "text", value: line.slice(lastIndex, m.index) });
    }
    if (m[1] !== undefined) tokens.push({ kind: "bold", value: m[1] });
    else if (m[2] !== undefined) tokens.push({ kind: "cite", label: m[2] });
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < line.length) {
    tokens.push({ kind: "text", value: line.slice(lastIndex) });
  }
  return tokens;
}

export function AnswerProse({
  text,
  citations,
  activeCitation,
  onCitationActivate,
  staggered = true,
}: AnswerProseProps) {
  const paragraphs = text.split(/\n\n+/);
  return (
    <div className="read-serif text-bone text-pretty max-w-[64ch]">
      {paragraphs.map((p, i) => {
        const tokens = tokenize(p);
        const content = tokens.map((t, j) => {
          if (t.kind === "text") return <Fragment key={j}>{t.value}</Fragment>;
          if (t.kind === "bold") return <strong key={j}>{t.value}</strong>;
          const c = citations.find((c) => c.label === t.label);
          const isActive = activeCitation === t.label;
          return (
            <button
              key={j}
              type="button"
              className="cite"
              data-active={isActive}
              onMouseEnter={() => onCitationActivate(t.label)}
              onMouseLeave={() => onCitationActivate(null)}
              onClick={() => onCitationActivate(t.label)}
              aria-label={c ? `Citation ${t.label}: ${c.title}` : `Citation ${t.label}`}
            >
              {t.label}
            </button>
          );
        });
        if (!staggered) return <p key={i}>{content}</p>;
        return (
          <motion.p
            key={i}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              delay: i * 0.12,
              duration: 0.7,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {content}
          </motion.p>
        );
      })}
    </div>
  );
}
