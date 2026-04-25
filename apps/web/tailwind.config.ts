import type { Config } from "tailwindcss";

/**
 * Tokens are derived directly from docs/Designs/BriefAlpha.pen.
 * Frame fFOSV (Screen / Desktop Main v5 中文版) and uOtTm (Judgement Drawer 中文版)
 * are canonical. Do not introduce new colors without updating both the canvas
 * and these tokens.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces
        canvas: "#FAFAF7",
        surface: "#FFFFFF",
        warningWash: "#FDF4EE",
        consentWash: "#FFF8F0",

        // Ink (text)
        ink: {
          900: "#0F0F0E",
          700: "#2A2A28",
          500: "#5C5C58",
          400: "#6E6E68",
          300: "#A8A8A3",
        },

        // Lines
        line: "#E8E7E1",
        lineSoft: "#D7DCE2",

        // Accent / status
        orange: {
          50: "#FFF8F0",
          200: "#FDBA74",
          600: "#C2410C",
        },
        success: "#15803D",
        danger: "#DC2626",
        warning: "#B45309",

        // Treemap fixed palette (must match design)
        treemap: {
          nvda: "#7F1D1D",
          tencent: "#15803D",
          aapl: "#EF4444",
          msft: "#FCA5A5",
          tlt: "#9AA8BA",
          baba: "#86EFAC",
          gld: "#FDE68A",
          cash: "#EDEDED",
          tsla: "#DC2626",
          mtn: "#BBF7D0",
        },
      },
      fontFamily: {
        // Loaded via app/layout.tsx with next/font/google
        serif: ["var(--font-fraunces)", "Fraunces", "Georgia", "serif"],
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Canonical sizes captured from the canvas
        "headline-xl": ["30px", { lineHeight: "1.08", fontWeight: "500" }],
        "headline-md": ["24px", { lineHeight: "1.15", fontWeight: "500" }],
        "judgement-title": ["16px", { lineHeight: "1.35", fontWeight: "500" }],
        "evidence-quote": ["16px", { lineHeight: "1.35", fontWeight: "500" }],
        "ai-summary": ["14px", { lineHeight: "1.55", fontWeight: "400" }],
        "meta-mono": ["11px", { lineHeight: "1.45", fontWeight: "400" }],
        "label-mono": ["10px", { lineHeight: "1.5", fontWeight: "500" }],
      },
      borderRadius: {
        chip: "2px",
        card: "4px",
      },
      boxShadow: {
        drawer: "-10px 0 36px rgba(15, 15, 14, 0.10)",
      },
    },
  },
  plugins: [],
};

export default config;
