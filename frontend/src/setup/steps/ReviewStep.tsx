import { useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { finish } from "../../api/setup";
import { clearAllWizardStorage } from "../storage";
import { FirstRunSummary } from "./FirstRunSummary";

export function ReviewStep({
  totalSteps,
  onBack,
}: {
  totalSteps: number;
  onBack: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  const onFinish = async () => {
    setFinishing(true);
    try {
      const { redirect } = await finish();
      clearAllWizardStorage();
      window.location.href = redirect;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish.");
    } finally {
      setFinishing(false);
    }
  };

  return (
    <WizardShell
      title="Review"
      stepIndex={totalSteps - 1}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onFinish}
          nextLabel="Finish"
          loading={finishing}
        />
      }
    >
      {error ? (
        <p className="mb-3 text-sm text-feedback-error" role="alert">
          {error}
        </p>
      ) : null}
      <FirstRunSummary />
    </WizardShell>
  );
}
