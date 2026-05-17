import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type {
  AssistantMessage,
  Citation,
  EvidenceItem,
  SourceType,
} from "@/lib/types";

interface EvidencePanelProps {
  message: AssistantMessage | null;
  activeCitation: string | null;
  open: boolean;
  onClose: () => void;
  onCitationActivate: (label: string | null) => void;
}

export function EvidencePanel({
  message,
  activeCitation,
  open,
  onClose,
  onCitationActivate,
}: EvidencePanelProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          key="evidence-panel"
          initial={{ x: 60, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 60, opacity: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex h-full w-[400px] shrink-0 flex-col bg-ink-deep"
        >
          <div className="absolute inset-y-0 left-0 w-px bg-ink-rule" />

          <div className="flex items-baseline justify-between px-7 pt-7 pb-6">
            <div className="ui-label text-bone-mute">
              evidence ·{" "}
              <span className="text-bone-soft">
                {message?.response.evidence_items.length ?? 0}
              </span>
            </div>
            <button
              onClick={onClose}
              aria-label="Close evidence panel"
              className="font-mono text-[14px] text-bone-mute transition-colors duration-200 hover:text-ember"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-7 pb-10">
            {message ? (
              <EvidenceList
                items={message.response.evidence_items}
                citations={message.response.citations}
                activeCitation={activeCitation}
                onCitationActivate={onCitationActivate}
              />
            ) : (
              <p className="font-serif text-[14px] italic leading-[1.5] text-bone-mute">
                Pick a citation to inspect.
              </p>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function EvidenceList({
  items,
  citations,
  activeCitation,
  onCitationActivate,
}: {
  items: EvidenceItem[];
  citations: Citation[];
  activeCitation: string | null;
  onCitationActivate: (label: string | null) => void;
}) {
  if (items.length === 0) return null;
  const labelMap = new Map(citations.map((c) => [c.source_id, c.label]));
  return (
    <ol className="space-y-7">
      {items.map((item, idx) => {
        const label = labelMap.get(item.source_id) ?? String(idx + 1);
        return (
          <EvidenceCard
            key={item.evidence_id}
            item={item}
            label={label}
            active={activeCitation === label}
            onCitationActivate={onCitationActivate}
            index={idx}
          />
        );
      })}
    </ol>
  );
}

const sourceLabels: Record<SourceType, string> = {
  guideline: "guideline",
  review: "review",
  trial: "trial",
  label: "drug label",
  registry: "registry",
  study: "study",
};

function EvidenceCard({
  item,
  label,
  active,
  onCitationActivate,
  index,
}: {
  item: EvidenceItem;
  label: string;
  active: boolean;
  onCitationActivate: (label: string | null) => void;
  index: number;
}) {
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (active && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [active]);

  return (
    <motion.li
      ref={ref}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: index * 0.08,
        duration: 0.6,
        ease: [0.22, 1, 0.36, 1],
      }}
      onMouseEnter={() => onCitationActivate(label)}
      onMouseLeave={() => onCitationActivate(null)}
      className="relative cursor-pointer"
    >
      {active && (
        <motion.span
          layoutId="evidence-active"
          className="absolute -inset-x-3 -inset-y-3 -z-10 rounded-sm bg-ember-mist"
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        />
      )}

      <div className="flex items-baseline gap-3">
        <span
          className={`font-mono text-[11px] tabular-nums transition-colors duration-300 ${
            active ? "text-ember" : "text-bone-deep"
          }`}
        >
          {label.padStart(2, "0")}
        </span>
        <span className="ui-label">{sourceLabels[item.source_type]}</span>
      </div>

      <h3
        className={`mt-1.5 font-serif text-[15px] leading-[1.35] text-pretty transition-colors duration-300 ${
          active ? "text-bone" : "text-bone-soft"
        }`}
        style={{ fontVariationSettings: '"opsz" 15' }}
      >
        {item.title}
      </h3>

      <div className="mt-1 font-mono text-[10.5px] tabular-nums text-bone-deep">
        {item.publisher}
        {item.publisher && item.publication_date && " · "}
        {item.publication_date && formatDate(item.publication_date)}
      </div>

      <p
        className="mt-3 font-serif text-[13.5px] italic leading-[1.55] text-bone-mute text-pretty"
        style={{ fontVariationSettings: '"opsz" 14' }}
      >
        {item.key_claim}
      </p>

      {item.safety_notes.length > 0 && (
        <p
          className="mt-2.5 font-serif text-[12.5px] leading-[1.55] text-bone-deep text-pretty"
          style={{ fontVariationSettings: '"opsz" 13' }}
        >
          <span className="ui-label mr-1.5 tracking-wide text-bone-deep">safety,</span>
          {item.safety_notes.join(" ")}
        </p>
      )}

      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 inline-flex items-baseline gap-1.5 font-mono text-[10.5px] tracking-wide text-bone-mute transition-colors duration-200 hover:text-ember"
      >
        <span>open source</span>
        <span>↗</span>
      </a>
    </motion.li>
  );
}

function formatDate(iso: string): string {
  return new Date(iso)
    .toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
    .toLowerCase();
}
