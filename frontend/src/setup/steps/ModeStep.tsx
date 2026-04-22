import { useState } from "react";
import { User, Users } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { setMode } from "../../api/setup";
import type { Mode } from "../../api/setup";

interface Props {
  envLocked: boolean;
  initialMode: Mode | null;
  onSaved: (mode: Mode) => void;
}

function ModeCard({
  title,
  description,
  icon: Icon,
  selected,
  disabled,
  onClick,
  envBadge,
}: {
  title: string;
  description: string;
  icon: typeof User;
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
  envBadge?: boolean;
}) {
  const base =
    "flex-1 p-6 border rounded-[--radius-lg] bg-[--color-bg-elevated] cursor-pointer text-left transition-colors";
  const selectedCls = "border-[--color-accent-primary] ring-2 ring-[--focus-ring-color]";
  const unselectedCls = "border-[--color-border-subtle] hover:border-[--color-border-secondary]";
  const disabledCls = "opacity-50 cursor-not-allowed";

  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${selected ? selectedCls : unselectedCls} ${disabled ? disabledCls : ""}`}
    >
      <div className="flex items-start justify-between">
        <Icon size={32} className="text-[--color-accent-primary]" />
        {envBadge ? (
          <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded-[--radius-sm] bg-[--color-surface-active] text-[--color-text-tertiary]">
            from environment
          </span>
        ) : null}
      </div>
      <div className="text-lg font-semibold text-[--color-text-primary] mt-3 mb-1">{title}</div>
      <div className="text-sm text-[--color-text-secondary] leading-relaxed">{description}</div>
    </button>
  );
}

export function ModeStep({ envLocked, initialMode, onSaved }: Props) {
  const [selected, setSelected] = useState<Mode | null>(initialMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onNext = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      await setMode(selected);
      onSaved(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save mode.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Welcome"
      stepIndex={0}
      totalSteps={5}
      footer={<WizardFooter onNext={onNext} nextDisabled={!selected} loading={loading} />}
    >
      <p className="text-sm text-[--color-text-secondary] mb-6">
        Pick how you'll run OpenLIA. You can change this later by resetting the wizard.
      </p>
      <div className="flex gap-4">
        <ModeCard
          title="Personal"
          description="Single user on localhost. No auth. Fastest path to trying OpenLIA."
          icon={User}
          selected={selected === "personal"}
          disabled={envLocked && initialMode !== "personal"}
          envBadge={envLocked && initialMode === "personal"}
          onClick={() => !envLocked && setSelected("personal")}
        />
        <ModeCard
          title="Company"
          description="Multi-user deployment with logins and invite-gated signup. Binds to 0.0.0.0 by default."
          icon={Users}
          selected={selected === "company"}
          disabled={envLocked && initialMode !== "company"}
          envBadge={envLocked && initialMode === "company"}
          onClick={() => !envLocked && setSelected("company")}
        />
      </div>
      {error ? <p className="text-sm text-[--color-feedback-error] mt-4">{error}</p> : null}
      <p className="text-xs text-[--color-text-tertiary] mt-8">
        Trying to use a company deployment someone else set up? Close this and open the URL your
        admin gave you — no install needed.
      </p>
    </WizardShell>
  );
}
