import { useState } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  tickers: string[];
  selected: string | null; // null = "All"
  onSelect: (ticker: string | null) => void;
  onAdd: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  onImportFromPortfolio?: () => void;
}

const PILL_BASE =
  "inline-flex items-center gap-1.5 h-7 px-3 rounded-full border text-[12px] font-medium transition-colors duration-[--duration-normal] ease-[--ease-out]";
const PILL_INACTIVE =
  "border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:border-[--color-border-strong]";
const PILL_ACTIVE =
  "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]";

export function TickerSelector({
  tickers,
  selected,
  onSelect,
  onAdd,
  onRemove,
  onImportFromPortfolio,
}: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const tooMany = tickers.length >= 21;

  const commitAdd = () => {
    const next = draft.trim().toUpperCase();
    if (next) {
      onAdd(next);
      setDraft("");
      setAdding(false);
    }
  };

  return (
    <div className="space-y-2">
      <div
        className="flex items-center gap-2 overflow-x-auto py-1"
        data-testid="ticker-selector"
      >
        <button
          type="button"
          onClick={() => onSelect(null)}
          className={`${PILL_BASE} ${selected === null ? PILL_ACTIVE : PILL_INACTIVE}`}
          data-testid="ticker-pill-all"
        >
          {t("retail_sentiment.ticker_selector.all")}
          <span
            className="font-mono"
            style={{ fontSize: "9px", letterSpacing: "0.1em" }}
          >
            {tickers.length}
          </span>
        </button>

        {tickers.map((tk) => {
          const active = selected === tk;
          return (
            <span key={tk} className="group relative inline-flex shrink-0">
              <button
                type="button"
                onClick={() => onSelect(tk)}
                data-testid={`ticker-pill-${tk}`}
                className={[
                  PILL_BASE,
                  active ? PILL_ACTIVE : PILL_INACTIVE,
                  "pr-6",
                ].join(" ")}
              >
                <span className="font-mono tracking-[0.02em]">{tk}</span>
              </button>
              <button
                type="button"
                aria-label={t("retail_sentiment.ticker_selector.remove_aria", { ticker: tk })}
                onClick={() => onRemove(tk)}
                className={[
                  "absolute right-1.5 top-1/2 -translate-y-1/2",
                  "inline-flex items-center justify-center w-3.5 h-3.5 rounded-full",
                  "text-[11px] leading-none",
                  active
                    ? "text-[--color-accent-on]"
                    : "text-[--color-text-tertiary] hover:text-[--color-text-primary]",
                  "opacity-0 group-hover:opacity-100 focus:opacity-100",
                ].join(" ")}
              >
                ×
              </button>
            </span>
          );
        })}

        {adding ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitAdd();
              } else if (e.key === "Escape") {
                setAdding(false);
                setDraft("");
              }
            }}
            onBlur={commitAdd}
            placeholder={t("retail_sentiment.ticker_selector.input_placeholder")}
            className="w-24 h-7 px-3 rounded-full border border-dashed border-[--color-border-strong] bg-[--color-bg-input] text-[12px] font-mono uppercase tracking-[0.04em] focus:outline-none focus:border-[--color-accent-primary]"
            data-testid="ticker-add-input"
          />
        ) : (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className={[
              "inline-flex items-center gap-1.5 h-7 px-3 rounded-full border border-dashed",
              "border-[--color-border-strong] text-[--color-text-secondary]",
              "bg-transparent text-[12px] hover:text-[--color-text-primary] hover:border-[--color-accent-primary]",
              "transition-colors duration-[--duration-normal] ease-[--ease-out]",
            ].join(" ")}
            data-testid="ticker-add-button"
          >
            {t("retail_sentiment.ticker_selector.add")}
          </button>
        )}

        {onImportFromPortfolio ? (
          <button
            type="button"
            onClick={onImportFromPortfolio}
            data-testid="ticker-import-portfolio"
            className={[
              "inline-flex items-center gap-1.5 h-7 px-3 rounded-full border border-dashed",
              "border-[--color-border-strong] text-[--color-text-secondary]",
              "bg-transparent text-[12px] hover:text-[--color-text-primary] hover:border-[--color-accent-primary]",
              "transition-colors duration-[--duration-normal] ease-[--ease-out]",
            ].join(" ")}
          >
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 7h4l2-2h6a2 2 0 0 1 2 2v3" />
              <path d="M3 7v11a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M16 14h5m0 0-2-2m2 2-2 2" />
            </svg>
            {t("retail_sentiment.ticker_selector.import_from_portfolio")}
          </button>
        ) : null}
      </div>

      {tooMany ? (
        <div
          data-testid="ticker-warning"
          className="rounded-md border border-[--color-feedback-warning] bg-[--color-feedback-warning-bg] px-3 py-1.5 text-[11px] text-[--color-feedback-warning]"
        >
          {t("retail_sentiment.ticker_selector.warning", { count: tickers.length })}
        </div>
      ) : null}
    </div>
  );
}
