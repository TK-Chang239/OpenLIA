import { useState } from "react";
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import { RefreshCw, FileText, Globe, Briefcase, BarChart3 } from "lucide-react";
import {
  SUGGESTION_BANK,
  pickSuggestions,
  type Suggestion,
  type SuggestionDept,
} from "./suggestionsBank";
import { localDaySeed } from "./greetings";

const DEPT_ICON: Record<SuggestionDept, JSX.Element> = {
  earnings_update: <FileText size={11} strokeWidth={1.5} />,
  macro_research: <Globe size={11} strokeWidth={1.5} />,
  portfolio: <Briefcase size={11} strokeWidth={1.5} />,
  retail_sentiment: <BarChart3 size={11} strokeWidth={1.5} />,
};

export function SuggestedGrid(): JSX.Element {
  const navigate = useNavigate();
  const [seedSalt, setSeedSalt] = useState(0);
  const seed = `${localDaySeed()}#${seedSalt}`;
  const suggestions = pickSuggestions(SUGGESTION_BANK, seed);

  const onCardClick = (s: Suggestion) => {
    navigate(`/secretary?prompt=${encodeURIComponent(s.question)}`);
  };

  return (
    <section>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-text-tertiary">
          Suggested · today
        </span>
        <button
          type="button"
          onClick={() => setSeedSalt((s) => s + 1)}
          className="inline-flex items-center gap-[6px] font-mono text-[10px] tracking-[0.06em] text-text-secondary cursor-pointer hover:text-text-primary transition-colors duration-normal ease-out"
        >
          Refresh <RefreshCw size={10} strokeWidth={1.5} />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-[10px] mt-[10px]">
        {suggestions.map((s) => (
          <button
            key={`${s.dept}-${s.question}`}
            type="button"
            onClick={() => onCardClick(s)}
            className="group p-[14px] bg-bg-elevated border border-border-subtle rounded-[10px] cursor-pointer transition-all duration-normal ease-out flex flex-col gap-2 text-left hover:border-border-strong hover:bg-surface-hover hover:-translate-y-[1px]"
          >
            <span className="flex items-center gap-2 font-mono text-[9px] tracking-[0.1em] uppercase text-text-tertiary">
              <span
                aria-hidden="true"
                className={`w-[5px] h-[5px] rounded-full ${s.live ? "bg-accent-primary" : "bg-border-strong"}`}
              />
              {s.tag}
            </span>
            <span className="text-[14px] leading-[1.45] text-text-primary font-medium">
              {s.question}
            </span>
            <span className="flex items-center gap-[6px] mt-[2px] font-mono text-[9px] tracking-[0.06em] text-text-tertiary">
              {DEPT_ICON[s.dept]}
              {s.sourceHint}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
