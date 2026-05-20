import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useWizard, WizardProvider } from "../setup/WizardContext";
import { ModeStep } from "../setup/steps/ModeStep";
import { IdentityStep } from "../setup/steps/IdentityStep";
import { AdminAccountStep } from "../setup/steps/AdminAccountStep";
import { ModelsStep } from "../setup/steps/ModelsStep";
import { ConnectorsStep } from "../setup/steps/ConnectorsStep";
import { AccessControlStep } from "../setup/steps/AccessControlStep";
import { ReviewStep } from "../setup/steps/ReviewStep";
import { getSetupState } from "../api/setup";

function Inner() {
  const { t } = useTranslation();
  const wizard = useWizard();
  const setupState = useSetupState();
  if (wizard.state === "loading") {
    return <div className="p-8 text-sm text-text-secondary">{t("auth.setup.loading")}</div>;
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
          {t("auth.setup.retry")}
        </button>
      </div>
    );
  }

  const { status, refresh, goBack, viewStep } = wizard;
  const total = status.mode === "company" ? 6 : 5;
  const step = viewStep ?? status.current_step;
  const envLocked = !!status.env_overrides.mode;
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
        enabledDepartmentIds={setupState.enabled_department_ids}
        systemRoleIds={setupState.system_role_ids}
        onBack={onBack}
        onSaved={refresh}
      />
    );
  if (step === "providers")
    return <ConnectorsStep totalSteps={total} onBack={onBack} onSaved={refresh} />;
  if (step === "access_control")
    return <AccessControlStep onBack={onBack} onSaved={refresh} />;
  if (step === "review")
    return <ReviewStep totalSteps={total} onBack={onBack} />;
  return <div className="p-8">{t("auth.setup.unknown_step", { step })}</div>;
}

function useSetupState(): { enabled_department_ids: string[]; system_role_ids: string[] } {
  const [state, setState] = useState<{
    enabled_department_ids: string[];
    system_role_ids: string[];
  }>({ enabled_department_ids: [], system_role_ids: [] });
  useEffect(() => {
    let cancelled = false;
    getSetupState()
      .then((resp) => {
        if (cancelled) return;
        setState({
          enabled_department_ids: resp.enabled_department_ids,
          system_role_ids: resp.system_role_ids,
        });
      })
      .catch(() => {
        // Fall back to empty arrays; the assign screen will show no slots.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}

export function SetupPage() {
  return (
    <WizardProvider>
      <Inner />
    </WizardProvider>
  );
}
