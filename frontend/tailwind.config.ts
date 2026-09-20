import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // MyWork AI — original dark-first identity.
        base: {
          950: "#07080c",
          900: "#0a0c12",
          850: "#0e111a",
          800: "#131722",
          750: "#181d2b",
          700: "#1f2534",
          600: "#2a3142",
        },
        ink: {
          50: "#f6f8fc",
          100: "#e6eaf3",
          200: "#cbd3e3",
          300: "#a7b1c8",
          400: "#7d88a3",
          500: "#5b6580",
          600: "#444d64",
          700: "#333a4d",
        },
        accent: {
          DEFAULT: "#6d8bff",
          soft: "#8aa2ff",
          deep: "#4f6ef0",
        },
        violet: { DEFAULT: "#a06bff" },
        teal: { DEFAULT: "#3fd0c9" },
        signal: {
          urgent: "#ff6b6b",
          warn: "#ffb454",
          ok: "#4ade80",
          info: "#6d8bff",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 40px -24px rgba(0,0,0,0.7)",
        glow: "0 0 0 1px rgba(109,139,255,0.35), 0 12px 40px -12px rgba(109,139,255,0.45)",
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)",
        "aurora":
          "radial-gradient(60% 60% at 15% 0%, rgba(109,139,255,0.14), transparent 60%), radial-gradient(40% 40% at 90% 10%, rgba(160,107,255,0.10), transparent 60%)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "70%": { transform: "scale(1.6)", opacity: "0" },
          "100%": { opacity: "0" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.8s infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4,0,0.6,1) infinite",
        "fade-up": "fade-up 0.35s ease-out both",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;