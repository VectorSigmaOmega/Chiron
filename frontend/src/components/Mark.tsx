import { motion } from "framer-motion";

export function Wordmark({
  size = "md",
  tone = "bone",
}: {
  size?: "sm" | "md" | "lg" | "xl";
  tone?: "bone" | "ember" | "mute";
}) {
  const sizes = {
    sm: "text-[15px]",
    md: "text-[19px]",
    lg: "text-[28px]",
    xl: "text-[40px]",
  } as const;
  const tones = {
    bone: "text-bone",
    ember: "text-ember",
    mute: "text-bone-soft",
  } as const;
  const opszMap = { sm: 14, md: 20, lg: 28, xl: 40 } as const;
  return (
    <span
      className={`inline-flex items-baseline gap-[5px] display-serif font-light ${sizes[size]} ${tones[tone]}`}
      style={{ fontVariationSettings: `"opsz" ${opszMap[size]}` }}
    >
      <span className="relative">
        chiron
        <motion.span
          aria-hidden
          className="absolute -right-[6px] bottom-[3px] inline-block h-[4px] w-[4px] rounded-full bg-ember"
          animate={{
            opacity: [0.45, 1, 0.45],
            boxShadow: [
              "0 0 0px oklch(0.78 0.155 72 / 0.0)",
              "0 0 10px oklch(0.78 0.155 72 / 0.8)",
              "0 0 0px oklch(0.78 0.155 72 / 0.0)",
            ],
          }}
          transition={{
            duration: 3.6,
            repeat: Infinity,
            ease: [0.4, 0, 0.6, 1],
          }}
        />
      </span>
    </span>
  );
}

/**
 * Luminous form for the empty state. A single open arc with a focal point,
 * drawn animated, surrounded by a soft amber breathing glow. Echoes the
 * Her OS aesthetic: one form, drenched field, vast quiet.
 */
export function ChironGlyph({
  size = 140,
  animate = true,
}: {
  size?: number;
  animate?: boolean;
}) {
  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size * 1.6, height: size * 1.6 }}
    >
      {/* breathing halo */}
      {animate && (
        <span
          aria-hidden
          className="absolute h-full w-full animate-ember-breathe rounded-full"
          style={{
            background:
              "radial-gradient(circle, oklch(0.78 0.155 72 / 0.55) 0%, oklch(0.78 0.155 72 / 0.12) 30%, transparent 60%)",
          }}
        />
      )}
      <svg
        width={size}
        height={size}
        viewBox="0 0 140 140"
        fill="none"
        className="relative text-ember"
      >
        <motion.path
          d="M 38 70 C 38 42, 76 30, 98 50 C 116 66, 110 92, 88 100 C 64 109, 40 96, 36 78"
          stroke="currentColor"
          strokeWidth="1.1"
          strokeLinecap="round"
          fill="none"
          initial={animate ? { pathLength: 0, opacity: 0 } : false}
          animate={animate ? { pathLength: 1, opacity: 1 } : undefined}
          transition={{ duration: 2.2, ease: [0.22, 1, 0.36, 1] }}
          style={{
            filter:
              "drop-shadow(0 0 14px oklch(0.78 0.155 72 / 0.6)) drop-shadow(0 0 4px oklch(0.78 0.155 72 / 0.8))",
          }}
        />
        <motion.circle
          cx="100"
          cy="70"
          r="2.5"
          fill="currentColor"
          initial={animate ? { opacity: 0, scale: 0 } : false}
          animate={animate ? { opacity: 1, scale: 1 } : undefined}
          transition={{ delay: 1.6, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          style={{
            filter:
              "drop-shadow(0 0 8px oklch(0.78 0.155 72 / 0.9)) drop-shadow(0 0 2px oklch(0.84 0.16 75 / 1))",
          }}
        />
      </svg>
    </div>
  );
}

/* A miniature glyph for inline use, e.g. the assistant thinking indicator */
export function MiniGlyph({ size = 14 }: { size?: number }) {
  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 14 14"
      fill="none"
      className="text-ember"
      animate={{ opacity: [0.5, 1, 0.5] }}
      transition={{
        duration: 2.4,
        repeat: Infinity,
        ease: [0.4, 0, 0.6, 1],
      }}
    >
      <path
        d="M 4 7 C 4 4.4, 8 3.3, 10 5 C 11.5 6.4, 11 8.7, 9 9.6 C 7 10.4, 5 9.4, 4 8"
        stroke="currentColor"
        strokeWidth="0.9"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="10.2" cy="7" r="0.7" fill="currentColor" />
    </motion.svg>
  );
}
