import { Settings } from "lucide-react";
import { useRef, useState } from "react";

import { ReportSettingsModal } from "../../components/equity-research/ReportSettingsModal";
import { SuggestionChips } from "../../components/equity-research/SuggestionChips";
import { useErConfig } from "../../hooks/useErConfig";

export default function EquityResearch() {
  const { config, loading, patch } = useErConfig();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [active, setActive] = useState(false);

  const onChipSelect = (value: string) => {
    setInput(value);
    inputRef.current?.focus();
  };

  const onSend = () => {
    if (!input.trim()) return;
    setActive(true);
    // Plan 12's useChatStream wiring will be injected here in a follow-up commit.
  };

  if (loading || !config) {
    return (
      <div className="p-6 text-sm text-[--color-text-tertiary]">Loading…</div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex-shrink-0 flex items-center justify-between border-b border-[--color-border-subtle] px-6">
        <h1 className="text-xl font-semibold">Equity Research</h1>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className="inline-flex items-center gap-2 h-8 px-3 text-sm border border-[--color-border-secondary] rounded-[--radius-md] text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          <Settings size={16} /> Report Settings
        </button>
      </header>

      {!active && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">Equity Research</h2>
            <p className="mt-2 text-md text-[--color-text-secondary]">
              Research companies, sectors, and market trends
            </p>
          </div>
          <SuggestionChips onSelect={onChipSelect} />
        </div>
      )}

      {active && (
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {/* Chat transcript renders here via Plan 12's ChatInterface in a follow-up commit */}
        </div>
      )}

      <div className="flex-shrink-0 px-6 py-4 border-t border-[--color-border-subtle]">
        <div className="max-w-[680px] mx-auto flex items-end gap-2">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            placeholder={
              active
                ? "Ask a follow-up question about the company, sector, or report..."
                : "Enter a ticker, company, or sector (e.g., AAPL, Semiconductors)..."
            }
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            className="flex-1 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3 text-md resize-none"
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!input.trim()}
            aria-label="Send"
            className="w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white disabled:opacity-40"
          >
            ↑
          </button>
        </div>
      </div>

      <ReportSettingsModal
        open={settingsOpen}
        config={config}
        onClose={() => setSettingsOpen(false)}
        onSave={async (p) => {
          await patch(p);
        }}
      />
    </div>
  );
}
