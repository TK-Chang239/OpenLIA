import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export type RedirectDepartment =
  | 'equity_research'
  | 'earnings_update'
  | 'morning_briefing'
  | 'retail_sentiment'
  | 'macro_research'
  | 'portfolio';

export interface RedirectCardProps {
  department: RedirectDepartment;
  reason: string;
  prefill?: string;
}

const DEPT_LABEL: Record<RedirectDepartment, string> = {
  equity_research: 'Equity Research',
  earnings_update: 'Earnings Updates',
  morning_briefing: 'Morning Briefings',
  retail_sentiment: 'Retail Sentiment',
  macro_research: 'Macro Research',
  portfolio: 'Portfolio',
};

const DEPT_PATH: Record<RedirectDepartment, string> = {
  equity_research: '/equity-research',
  earnings_update: '/earnings-update',
  morning_briefing: '/morning-briefings',
  retail_sentiment: '/retail-sentiment',
  macro_research: '/macro-research',
  portfolio: '/portfolio',
};

export function RedirectCard({ department, reason, prefill }: RedirectCardProps) {
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const label = DEPT_LABEL[department];
  const go = () => {
    const base = DEPT_PATH[department];
    const target = prefill ? `${base}?q=${encodeURIComponent(prefill)}` : base;
    navigate(target);
  };

  return (
    <div className="redirect-card" role="group" aria-label={`Suggested redirect to ${label}`}>
      <p className="redirect-card__text">
        This looks like a <strong>{label}</strong> request. {reason}
      </p>
      <div className="redirect-card__divider" />
      <div className="redirect-card__actions">
        <button type="button" className="redirect-card__primary" onClick={go}>
          Go to {label}
          <ArrowRight size={14} aria-hidden />
        </button>
        <button
          type="button"
          className="redirect-card__secondary"
          onClick={() => setDismissed(true)}
        >
          Stay here
        </button>
      </div>
    </div>
  );
}
