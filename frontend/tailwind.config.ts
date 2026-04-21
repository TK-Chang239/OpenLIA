import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-app": "var(--color-bg-app)",
        "bg-elevated": "var(--color-bg-elevated)",
        "sidebar-bg": "var(--color-sidebar-bg)",
        "surface-hover": "var(--color-surface-hover)",
        "surface-active": "var(--color-surface-active)",
        "accent-primary": "var(--color-accent-primary)",
        "accent-subtle": "var(--color-accent-subtle)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-tertiary": "var(--color-text-tertiary)",
        "icon-primary": "var(--color-icon-primary)",
        "border-subtle": "var(--color-border-subtle)",
      },
      borderRadius: {
        md: "var(--radius-md)",
      },
    },
  },
  plugins: [],
};

export default config;
