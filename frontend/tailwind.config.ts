import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-base": "var(--color-bg-base)",
        "bg-app": "var(--color-bg-base)", // alias — retired
        "bg-elevated": "var(--color-bg-elevated)",
        "bg-input": "var(--color-bg-input)",
        "bg-code": "var(--color-bg-code)",
        "sidebar-bg": "var(--color-sidebar-bg)",

        "surface-hover": "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",
        "surface-subtle": "var(--color-surface-subtle)",

        "accent-primary": "var(--color-accent-primary)",
        "accent-hover": "var(--color-accent-hover)",
        "accent-subtle": "var(--color-accent-subtle)",
        "accent-on": "var(--color-accent-on)",

        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-tertiary": "var(--color-text-tertiary)",
        "text-on-accent": "var(--color-text-on-accent)",

        "icon-primary": "var(--color-icon-primary)",
        "icon-active": "var(--color-icon-active)",
        "icon-muted": "var(--color-icon-muted)",

        "border-subtle": "var(--color-border-subtle)",
        "border-secondary": "var(--color-border-secondary)",
        "border-strong": "var(--color-border-strong)",

        "feedback-error": "var(--color-feedback-error)",
        "feedback-success": "var(--color-feedback-success)",
        "feedback-warning": "var(--color-feedback-warning)",
        "feedback-info": "var(--color-feedback-info)",

        "yellow-50": "var(--yellow-50)",
        "yellow-200": "var(--yellow-200)",
        "yellow-400": "var(--yellow-400)",
        "yellow-600": "var(--yellow-600)",
        "yellow-800": "var(--yellow-800)",
        "yellow-900": "var(--yellow-900)",
      },
      fontFamily: {
        display: "var(--font-display)",
        mono: "var(--font-mono)",
        serif: "var(--font-serif)",
      },
      fontSize: {
        label: ["var(--text-label)", { letterSpacing: "var(--tracking-label)" }],
        "label-sm": ["var(--text-label-sm)", { letterSpacing: "var(--tracking-micro)" }],
        data: ["var(--text-data)", { lineHeight: "var(--leading-relaxed)" }],
        greeting: ["var(--text-greeting)", { lineHeight: "1.3" }],
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "var(--radius-2xl)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        "input-focus": "var(--shadow-input-focus)",
        accent: "var(--shadow-accent)",
      },
      transitionDuration: {
        instant: "var(--duration-instant)",
        fast: "var(--duration-fast)",
        normal: "var(--duration-normal)",
        base: "var(--duration-normal)", // alias — retired
        slow: "var(--duration-slow)",
        xslow: "var(--duration-xslow)",
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
        in: "var(--ease-in)",
        "in-out": "var(--ease-in-out)",
        spring: "var(--ease-spring)",
      },
      ringColor: {
        focus: "var(--focus-ring-color)",
      },
      keyframes: {
        livePulse: {
          "0%, 100%": { opacity: "0.5" },
          "50%": { opacity: "1" },
        },
        feedFadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        feedFadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "live-pulse": "livePulse 1.6s var(--ease-in-out) infinite",
        "feed-fade-up": "feedFadeUp 480ms var(--ease-out) both",
        "feed-fade-in": "feedFadeIn 320ms var(--ease-out) both",
      },
    },
  },
  plugins: [],
};

export default config;
