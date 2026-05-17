/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        "ink-deep": "var(--ink-deep)",
        "ink-rise": "var(--ink-rise)",
        "ink-glow": "var(--ink-glow)",
        "ink-line": "var(--ink-line)",
        "ink-rule": "var(--ink-rule)",
        bone: "var(--bone)",
        "bone-soft": "var(--bone-soft)",
        "bone-mute": "var(--bone-mute)",
        "bone-deep": "var(--bone-deep)",
        ember: "var(--ember)",
        "ember-bright": "var(--ember-bright)",
        "ember-deep": "var(--ember-deep)",
        "ember-glow": "var(--ember-glow)",
        "ember-mist": "var(--ember-mist)",
        sage: "var(--sage)",
        "sage-glow": "var(--sage-glow)",
        rose: "var(--rose)",
        "rose-glow": "var(--rose-glow)",
        smoke: "var(--smoke)",
        "smoke-glow": "var(--smoke-glow)",
      },
      fontFamily: {
        serif: ["Newsreader", "Source Serif Pro", "Georgia", "serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
        sans: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
      },
      letterSpacing: {
        tight: "-0.018em",
        wide: "0.06em",
        wider: "0.12em",
      },
      transitionTimingFunction: {
        quart: "cubic-bezier(0.22, 1, 0.36, 1)",
        quint: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "ember-breathe": {
          "0%, 100%": {
            opacity: "0.55",
            transform: "scale(1)",
            filter: "blur(20px)",
          },
          "50%": {
            opacity: "1",
            transform: "scale(1.08)",
            filter: "blur(24px)",
          },
        },
        "dot-pulse": {
          "0%, 100%": { opacity: "0.5", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.4)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "trace-cursor": {
          "0%, 50%": { opacity: "1" },
          "51%, 100%": { opacity: "0" },
        },
      },
      animation: {
        "ember-breathe": "ember-breathe 3.6s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "dot-pulse": "dot-pulse 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        shimmer: "shimmer 2.4s linear infinite",
        "trace-cursor": "trace-cursor 1s steps(2) infinite",
      },
    },
  },
  plugins: [],
};
