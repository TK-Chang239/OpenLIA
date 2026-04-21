import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "var(--color-bg-app)",
        "bg-base": "var(--color-bg-base)",
        "bg-elevated": "var(--color-bg-elevated)",
        "bg-input": "var(--color-bg-input)",
        "sidebar-bg": "var(--color-sidebar-bg)",
        "surface-hover": "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",
        "accent-primary": "var(--color-accent-primary)",
        "accent-hover": "var(--color-accent-hover)",
        "accent-subtle": "var(--color-accent-subtle)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-tertiary": "var(--color-text-tertiary)",
        "icon-primary": "var(--color-icon-primary)",
        "border-subtle": "var(--color-border-subtle)",
        "border-secondary": "var(--color-border-secondary)",
        "feedback-error": "var(--color-feedback-error)",
        "feedback-success": "var(--color-feedback-success)",
        "feedback-warning": "var(--color-feedback-warning)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        base: "var(--duration-base)",
      },
      ringColor: {
        focus: "var(--focus-ring-color)",
      },
    },
  },
  plugins: [],
};

export default config;
