import { useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { TierSlotCard } from "./TierSlotCard";
import type { TierEntryWithStatus } from "./TierSlotCard";
import { saveModels } from "../../api/setup";

type TierName = "thinking" | "everyday" | "quick";

export function ModelsStep({
  totalSteps,
  requiredTiers,
  onBack,
  onSaved,
}: {
  totalSteps: number;
  requiredTiers: TierName[];
  onBack: () => void;
  onSaved: () => void;
}) {
  const [thinking, setThinking] = useState<TierEntryWithStatus[]>([]);
  const [everyday, setEveryday] = useState<TierEntryWithStatus[]>([]);
  const [quick, setQuick] = useState<TierEntryWithStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tierHasGreen = (entries: TierEntryWithStatus[]) => entries.some((e) => e.status === "ok");

  const canSubmit = useMemo(
    () =>
      requiredTiers.every((tier) => {
        if (tier === "thinking") return tierHasGreen(thinking);
        if (tier === "everyday") return tierHasGreen(everyday);
        return tierHasGreen(quick);
      }),
    [requiredTiers, thinking, everyday, quick],
  );

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await saveModels({
        thinking: thinking.filter((e) => e.status === "ok").map(stripUi),
        everyday: everyday.filter((e) => e.status === "ok").map(stripUi),
        quick: quick.filter((e) => e.status === "ok").map(stripUi),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save models.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="AI Models"
      stepIndex={2}
      totalSteps={totalSteps}
      footer={<WizardFooter onBack={onBack} onNext={onNext} nextDisabled={!canSubmit} loading={loading} />}
    >
      <p className="text-sm text-[--color-text-secondary] mb-4">
        OpenLIA uses a top-tier Thinking model for deep analysis, an Everyday model for general
        chat, and a Quick model for classification and lightweight jobs.
      </p>
      <p className="text-xs text-[--color-text-tertiary] mb-6">
        Required by your enabled departments: <strong>{requiredTiers.join(", ")}</strong>.
      </p>
      <TierSlotCard tierLabel="Thinking" tierValue="thinking" entries={thinking} onChange={setThinking} />
      <TierSlotCard tierLabel="Everyday" tierValue="everyday" entries={everyday} onChange={setEveryday} />
      <TierSlotCard tierLabel="Quick" tierValue="quick" entries={quick} onChange={setQuick} />
      {error ? <p className="text-sm text-[--color-feedback-error] mt-4">{error}</p> : null}
    </WizardShell>
  );
}

function stripUi(e: TierEntryWithStatus) {
  const { ui_id, status, error: _err, ...rest } = e;
  return rest;
}
