import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

interface ComposerProps {
  onSubmit: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}

export function Composer({
  onSubmit,
  disabled,
  placeholder = "ask",
  autoFocus,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 220) + "px";
  }, [value]);

  useEffect(() => {
    if (autoFocus) taRef.current?.focus();
  }, [autoFocus]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  const ready = value.trim().length > 0 && !disabled;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="relative w-full"
    >
      <div className="relative flex items-end gap-3 py-3">
        <span
          aria-hidden
          className="select-none font-serif text-[24px] italic leading-none text-ember"
          style={{ fontVariationSettings: '"opsz" 24' }}
        >
          ‹
        </span>
        <textarea
          ref={taRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          rows={1}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full resize-none bg-transparent font-serif text-[18px] leading-[1.55] text-bone placeholder:text-bone-deep focus:outline-none disabled:opacity-50"
          style={{ fontVariationSettings: '"opsz" 18' }}
        />
        <button
          type="submit"
          disabled={!ready}
          aria-label="Send"
          className="shrink-0 self-end pb-1.5 font-mono text-[11px] tracking-wide transition-all duration-300"
        >
          <motion.span
            animate={{
              opacity: ready ? 1 : 0.35,
              x: ready ? 0 : -4,
            }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className={`flex items-center gap-1.5 ${
              ready ? "text-ember" : "text-bone-deep"
            }`}
          >
            <span>send</span>
            <span>→</span>
          </motion.span>
        </button>
      </div>

      {/* Animated underline */}
      <div className="relative h-px w-full bg-ink-rule">
        <motion.div
          className="absolute inset-y-0 left-1/2 origin-center bg-ember"
          initial={false}
          animate={{
            width: focused || value ? "100%" : "0%",
            x: focused || value ? "-50%" : "0%",
          }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          style={{
            boxShadow: focused
              ? "0 0 12px oklch(0.78 0.155 72 / 0.5)"
              : "none",
          }}
        />
      </div>
    </form>
  );
}
