import { motion } from "framer-motion";
import type {
  AssistantMessage,
  ChatMessage,
  ErrorMessage,
  PendingMessage,
  TraceStep,
  UserMessage,
  Citation,
  AbstentionClass,
  EvidenceStrength,
} from "@/lib/types";
import { AnswerProse } from "./AnswerProse";

const fadeUp = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] },
};

/* ------------------------ User ------------------------ */

export function UserBlock({ message }: { message: UserMessage }) {
  return (
    <motion.div {...fadeUp} className="flex justify-end pl-12">
      <div className="relative max-w-[560px]">
        <span
          aria-hidden
          className="absolute -left-5 top-0 select-none font-serif text-[24px] italic leading-none text-ember"
          style={{ fontVariationSettings: '"opsz" 24' }}
        >
          ‹
        </span>
        <p
          className="font-serif text-[17px] italic leading-[1.5] text-bone-soft text-pretty"
          style={{ fontVariationSettings: '"opsz" 17' }}
        >
          {message.content}
        </p>
      </div>
    </motion.div>
  );
}

/* ------------------------ Assistant ------------------------ */

interface AssistantBlockProps {
  message: AssistantMessage;
  activeCitation: string | null;
  onCitationActivate: (label: string | null) => void;
  onSelectCitation: (citation: Citation) => void;
  onPickClarification?: (option: string) => void;
}

export function AssistantBlock(props: AssistantBlockProps) {
  const { response } = props.message;
  if (response.status === "answered") return <AnsweredBlock {...props} />;
  if (response.status === "needs_clarification")
    return <ClarificationBlock {...props} />;
  return <AbstentionBlock {...props} />;
}

/* ------------------------ Answered ------------------------ */

const strengthCopy: Record<EvidenceStrength, string> = {
  high: "strong evidence",
  moderate: "moderate evidence",
  low: "limited evidence",
  unknown: "indeterminate evidence",
};

function AnsweredBlock({
  message,
  activeCitation,
  onCitationActivate,
}: AssistantBlockProps) {
  const { response } = message;
  return (
    <motion.section {...fadeUp} className="pr-12">
      <AnswerProse
        text={response.answer ?? ""}
        citations={response.citations}
        activeCitation={activeCitation}
        onCitationActivate={onCitationActivate}
      />

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.8 }}
        className="mt-7 flex flex-wrap items-baseline gap-x-6 gap-y-1"
      >
        {response.evidence_strength && (
          <span className="font-mono text-[11px] tracking-wide text-bone-mute">
            <span className="text-ember">·</span>{" "}
            {strengthCopy[response.evidence_strength]}, {response.citations.length} cited
          </span>
        )}
        {response.last_literature_check_at && (
          <span className="font-mono text-[11px] tracking-wide text-bone-deep">
            literature read {formatStamp(response.last_literature_check_at)}
          </span>
        )}
      </motion.div>

      {response.limitations.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.1, duration: 0.8 }}
          className="mt-5 max-w-[60ch]"
        >
          <div className="rule-dotted mb-3" />
          <p
            className="font-serif text-[14px] italic leading-[1.55] text-bone-mute"
            style={{ fontVariationSettings: '"opsz" 14' }}
          >
            <span className="ui-label normal-case mr-2 tracking-wide text-bone-deep">
              caveat,
            </span>
            {response.limitations.join(" ")}
          </p>
        </motion.div>
      )}
    </motion.section>
  );
}

/* ------------------------ Clarification ------------------------ */

function ClarificationBlock({
  message,
  onPickClarification,
}: AssistantBlockProps) {
  const { response } = message;
  const text = response.clarification_question ?? "";
  return (
    <motion.section {...fadeUp} className="pr-12">
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-wider text-rose">
        clarifying
      </div>
      <AnswerProse
        text={text}
        citations={[]}
        activeCitation={null}
        onCitationActivate={() => {}}
      />
      {response.clarification_options &&
        response.clarification_options.length > 0 && (
          <div className="mt-5 flex flex-col gap-px max-w-[480px]">
            {response.clarification_options.map((opt, i) => (
              <motion.button
                key={opt}
                onClick={() => onPickClarification?.(opt)}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{
                  delay: 0.5 + i * 0.07,
                  duration: 0.5,
                  ease: [0.22, 1, 0.36, 1],
                }}
                whileHover={{ x: 3 }}
                className="group flex items-baseline gap-3 py-2 text-left"
              >
                <span className="font-mono text-[10px] tabular-nums text-bone-deep group-hover:text-rose transition-colors duration-200">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className="flex-1 font-serif text-[15px] italic leading-[1.45] text-bone-soft group-hover:text-bone transition-colors duration-200"
                  style={{ fontVariationSettings: '"opsz" 15' }}
                >
                  {opt}
                </span>
                <span className="font-mono text-[12px] text-bone-deep opacity-0 group-hover:opacity-100 group-hover:text-rose transition-all duration-200">
                  →
                </span>
              </motion.button>
            ))}
          </div>
        )}
    </motion.section>
  );
}

/* ------------------------ Abstention ------------------------ */

const abstentionLabels: Record<AbstentionClass, string> = {
  insufficient_evidence: "insufficient evidence",
  conflicting_evidence: "conflicting evidence",
  missing_clinical_context: "missing clinical context",
  coverage_gap: "coverage gap",
  recency_gap: "recency gap",
  ambiguous_query: "ambiguous query",
  out_of_scope: "outside supported scope",
};

function AbstentionBlock({ message }: AssistantBlockProps) {
  const { response } = message;
  const cls = response.abstention_class
    ? abstentionLabels[response.abstention_class]
    : "abstained";
  return (
    <motion.section {...fadeUp} className="pr-12">
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-wider text-smoke">
        declined · {cls}
      </div>
      <p
        className="read-serif text-bone-soft text-pretty max-w-[60ch]"
        style={{ fontVariationSettings: '"opsz" 17' }}
      >
        {response.abstention_reason}
      </p>
      {response.limitations.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 0.8 }}
          className="mt-5 max-w-[60ch]"
        >
          <div className="rule-dotted mb-3" />
          <p
            className="font-serif text-[14px] italic leading-[1.55] text-bone-mute"
            style={{ fontVariationSettings: '"opsz" 14' }}
          >
            {response.limitations.join(" ")}
          </p>
        </motion.div>
      )}
    </motion.section>
  );
}

/* ------------------------ Pending (orchestration trace) ------------------------ */

const agentNames: Record<TraceStep["agent"], string> = {
  parser: "parser",
  guideline: "guidelines",
  literature: "literature",
  drug_safety: "drug safety",
  trials: "trials",
  synthesizer: "synthesis",
  verifier: "verification",
};

export function PendingBlock({ message }: { message: PendingMessage }) {
  return (
    <motion.section {...fadeUp} className="pr-12">
      <div className="mb-4 flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-wider text-ember">
        <span className="inline-block h-1 w-1 rounded-full bg-ember animate-dot-pulse" />
        working
      </div>
      <ol className="space-y-2">
        {message.trace.map((step) => (
          <TraceLine key={step.id} step={step} />
        ))}
      </ol>
    </motion.section>
  );
}

function TraceLine({ step }: { step: TraceStep }) {
  const running = step.status === "running";
  const done = step.status === "done";
  const skipped = step.status === "skipped";
  const pending = step.status === "pending";

  return (
    <motion.li
      layout
      initial={false}
      className="flex items-baseline gap-3 font-mono text-[12.5px]"
    >
      <span
        className={`w-[110px] shrink-0 text-[10px] uppercase tracking-wider tabular-nums ${
          running
            ? "text-ember"
            : done
              ? "text-sage"
              : skipped
                ? "text-bone-deep line-through"
                : "text-bone-deep"
        }`}
      >
        {agentNames[step.agent]}
      </span>
      <span
        className={`flex-1 ${
          running
            ? "text-bone"
            : done
              ? "text-bone-soft"
              : skipped
                ? "text-bone-deep line-through decoration-bone-deep/40"
                : "text-bone-deep"
        }`}
      >
        {stripVerb(step.label)}
        {running && (
          <span className="ml-1 inline-block w-[7px] animate-trace-cursor bg-ember align-middle">
            &nbsp;
          </span>
        )}
      </span>
      {step.source_count !== undefined && !pending && !skipped && (
        <span className="font-mono text-[10.5px] tabular-nums text-bone-deep">
          {step.source_count}
        </span>
      )}
    </motion.li>
  );
}

function stripVerb(s: string): string {
  return s.replace(/^(Parsing|Consulting|Searching|Checking|Synthesizing|Verifying)\s+/, "").toLowerCase();
}

/* ------------------------ Error ------------------------ */

export function ErrorBlock({
  message,
  onRetry,
}: {
  message: ErrorMessage;
  onRetry: () => void;
}) {
  return (
    <motion.section {...fadeUp} className="pr-12">
      <div className="mb-3 font-mono text-[10.5px] uppercase tracking-wider text-rose">
        unable to complete
      </div>
      <p
        className="read-serif text-bone-soft text-pretty max-w-[60ch]"
        style={{ fontVariationSettings: '"opsz" 17' }}
      >
        {message.reason}
      </p>
      {message.retryable && (
        <button
          onClick={onRetry}
          className="group mt-4 flex items-center gap-2 font-mono text-[11px] tracking-wide text-rose transition-colors duration-200 hover:text-ember"
        >
          <span>retry</span>
          <span className="group-hover:translate-x-1 transition-transform duration-200">
            →
          </span>
        </button>
      )}
    </motion.section>
  );
}

/* ------------------------ Router ------------------------ */

export function MessageRouter({
  message,
  activeCitation,
  onCitationActivate,
  onSelectCitation,
  onPickClarification,
  onRetry,
}: {
  message: ChatMessage;
  activeCitation: string | null;
  onCitationActivate: (label: string | null) => void;
  onSelectCitation: (c: Citation) => void;
  onPickClarification?: (option: string) => void;
  onRetry: () => void;
}) {
  if (message.kind === "user") return <UserBlock message={message} />;
  if (message.kind === "assistant") {
    return (
      <AssistantBlock
        message={message}
        activeCitation={activeCitation}
        onCitationActivate={onCitationActivate}
        onSelectCitation={onSelectCitation}
        onPickClarification={onPickClarification}
      />
    );
  }
  if (message.kind === "pending") return <PendingBlock message={message} />;
  return <ErrorBlock message={message} onRetry={onRetry} />;
}

/* ------------------------ Utils ------------------------ */

function formatStamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).toLowerCase();
}
