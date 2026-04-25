import { useEffect, useState } from "react";
import { useWizard, WizardProvider } from "../setup/WizardContext";
import { ModeStep } from "../setup/steps/ModeStep";
import { IdentityStep } from "../setup/steps/IdentityStep";
import { AdminAccountStep } from "../setup/steps/AdminAccountStep";
import { ModelsStep } from "../setup/steps/ModelsStep";
import { ProvidersStep } from "../setup/steps/ProvidersStep";
import { AccessControlStep } from "../setup/steps/AccessControlStep";
import { ReviewStep } from "../setup/steps/ReviewStep";
import { getRequiredTiers } from "../api/setup";

type TierName = "thinking" | "everyday" | "quick";
const FALLBACK_TIERS: TierName[] = ["thinking", "everyday", "quick"];

function Inner() {
  const wizard = useWizard();
  if (wizard.state === "loading") {
    return <div className="p-8 text-sm text-text-secondary">Loading…</div>;
  }
  if (wizard.state === "error") {
    return (
      <div className="p-8">
        <p className="text-sm text-feedback-error">{wizard.message}</p>
        <button
          type="button"
          onClick={wizard.refresh}
          className="mt-3 h-9 px-3 rounded-md text-sm border border-border-secondary"
        >
          Retry
        </button>
      </div>
    );
  }

  const { status, refresh, goBack, viewStep } = wizard;
  const total = status.mode === "company" ? 6 : 5;
  const step = viewStep ?? status.current_step;
  const envLocked = !!status.env_overrides.mode;
  const requiredTiers = useRequiredTiers();
  const onBack = goBack ?? refresh;

  if (step === "mode")
    return (
      <ModeStep envLocked={envLocked} initialMode={envLocked ? status.mode : null} onSaved={refresh} />
    );
  if (step === "identity") return <IdentityStep onBack={onBack} onSaved={refresh} />;
  if (step === "admin") return <AdminAccountStep onBack={onBack} onSaved={refresh} />;
  if (step === "models")
    return (
      <ModelsStep
        totalSteps={total}
        requiredTiers={requiredTiers}
        onBack={onBack}
        onSaved={refresh}
      />
    );
  if (step === "providers")
    return <ProvidersStep totalSteps={total} onBack={onBack} onSaved={refresh} />;
  if (step === "access_control")
    return <AccessControlStep onBack={onBack} onSaved={refresh} />;
  if (step === "review")
    return <ReviewStep totalSteps={total} onBack={onBack} />;
  return <div className="p-8">Unknown step: {step}</div>;
}

function useRequiredTiers(): TierName[] {
  const [tiers, setTiers] = useState<TierName[]>(FALLBACK_TIERS);
  useEffect(() => {
    let cancelled = false;
    getRequiredTiers()
      .then((resp) => {
        if (cancelled) return;
        const valid = resp.required_tiers.filter((t): t is TierName =>
          (FALLBACK_TIERS as string[]).includes(t),
        );
        if (valid.length > 0) setTiers(valid);
      })
      .catch(() => {
        // Fall back to the default trio; do not block the wizard.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return tiers;
}

export function SetupPage() {
  return (
    <WizardProvider>
      <Inner />
    </WizardProvider>
  );
}
