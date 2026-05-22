import { useState } from "react";
import { fetchConversionPrompt } from "../../../api/report-templates";

export function ConversionPromptButton() {
  const [label, setLabel] = useState<"Convert" | "Copied!" | "Failed">("Convert");

  async function handleClick() {
    try {
      const prompt = await fetchConversionPrompt();
      await navigator.clipboard.writeText(prompt);
      setLabel("Copied!");
      setTimeout(() => setLabel("Convert"), 2000);
    } catch {
      setLabel("Failed");
      setTimeout(() => setLabel("Convert"), 2000);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      style={{
        padding: "0.25rem 0.625rem",
        fontSize: "0.8125rem",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "0.25rem",
        background: "var(--color-bg-elevated)",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}
