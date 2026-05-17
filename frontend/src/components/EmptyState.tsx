import { motion } from "framer-motion";
import { ChironGlyph, Wordmark } from "./Mark";
import { examplePrompts } from "@/lib/mockData";

interface EmptyStateProps {
  onPick: (prompt: string) => void;
}

export function EmptyState({ onPick }: EmptyStateProps) {
  return (
    <div className="relative mx-auto flex h-full w-full max-w-[640px] flex-col items-center justify-center px-8 py-10">
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
        className="mb-10"
      >
        <ChironGlyph size={132} animate />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="mb-3"
      >
        <Wordmark size="xl" />
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.4, duration: 1.0 }}
        className="display-serif max-w-[460px] text-balance text-center text-[16px] italic leading-[1.55] text-bone-soft"
        style={{ fontVariationSettings: '"opsz" 16' }}
      >
        Open-domain medical evidence. Cited, clarified, or declined.
      </motion.p>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.9, duration: 1.0 }}
        className="mt-14 flex w-full max-w-[520px] flex-col gap-px"
      >
        <div className="ui-label mb-3 text-center text-bone-deep">
          try
        </div>
        {examplePrompts.map((ex, i) => (
          <motion.button
            key={i}
            onClick={() => onPick(ex.prompt)}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              delay: 2.0 + i * 0.08,
              duration: 0.7,
              ease: [0.22, 1, 0.36, 1],
            }}
            whileHover={{ x: 2 }}
            className="group relative flex items-baseline gap-3 py-2.5 text-left"
          >
            <span className="font-mono text-[10px] uppercase tracking-wide text-bone-deep group-hover:text-ember/70 transition-colors duration-200">
              {ex.category.split(" ")[0]}
            </span>
            <span
              className="flex-1 font-serif text-[15px] italic leading-[1.45] text-bone-soft group-hover:text-bone transition-colors duration-200"
              style={{ fontVariationSettings: '"opsz" 15' }}
            >
              {ex.prompt}
            </span>
            <span className="font-mono text-[14px] text-bone-deep group-hover:text-ember group-hover:translate-x-1 transition-all duration-300">
              →
            </span>
          </motion.button>
        ))}
      </motion.div>
    </div>
  );
}
