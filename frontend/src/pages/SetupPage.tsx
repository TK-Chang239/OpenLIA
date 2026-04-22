import { useWizard, WizardProvider } from "../setup/WizardContext";
import { ModeStep } from "../setup/steps/ModeStep";
import { IdentityStep } from "../setup/steps/IdentityStep";
import { AdminAccountStep } from "../setup/steps/AdminAccountStep";
import { ModelsStep } from "../setup/steps/ModelsStep";
import { ProvidersStep } from "../setup/steps/ProvidersStep";
import { AccessControlStep } from "../setup/steps/AccessControlStep";
import { ReviewStep } from "../setup/steps/ReviewStep";

function Inner() {
  const wizard = useWizard();
  if (wizard.state === "loading") {
    return <div className="p-8 text-sm text-[--color-text-secondary]">Loading…</div>;
  }
  if (wizard.state === "error") {
    return (
      <div className="p-8">
        <p className="text-sm text-[--color-feedback-error]">{wizard.message}</p>
        <button
          type="button"
          onClick={wizard.refresh}
          className="mt-3 h-9 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary]"
        >
          Retry
        </button>
      </div>
    );
  }

  const { status, refresh } = wizard;
  const total = status.mode === "company" ? 6 : 5;
  const step = status.current_step;
  const envLocked = !!status.env_overrides.mode;

  if (step === "mode")
    return (
      <ModeStep envLocked={envLocked} initialMode={envLocked ? status.mode : null} onSaved={refresh} />
    );
  if (step === "identity") return <IdentityStep onBack={refresh} onSaved={refresh} />;
  if (step === "admin") return <AdminAccountStep onBack={refresh} onSaved={refresh} />;
  if (step === "models")
    return (
      <ModelsStep
        totalSteps={total}
        requiredTiers={["thinking", "everyday", "quick"]}
        onBack={refresh}
        onSaved={refresh}
      />
    );
  if (step === "providers")
    return <ProvidersStep totalSteps={total} onBack={refresh} onSaved={refresh} />;
  if (step === "access_control")
    return <AccessControlStep onBack={refresh} onSaved={refresh} />;
  if (step === "review")
    return <ReviewStep totalSteps={total} onBack={refresh} />;
  return <div className="p-8">Unknown step: {step}</div>;
}

export function SetupPage() {
  return (
    <WizardProvider>
      <Inner />
    </WizardProvider>
  );
}
