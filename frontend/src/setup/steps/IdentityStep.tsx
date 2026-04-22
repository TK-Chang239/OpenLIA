import { useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { Input } from "../../components/primitives/Input";
import { setIdentity } from "../../api/setup";

export function IdentityStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = displayName.trim().length >= 1 && displayName.trim().length <= 60;

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await setIdentity(displayName.trim());
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save identity.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Your name"
      stepIndex={1}
      totalSteps={5}
      footer={<WizardFooter onBack={onBack} onNext={onNext} nextDisabled={!valid} loading={loading} />}
    >
      <p className="text-sm text-[--color-text-secondary] mb-6">
        This is the name LIA departments will use when addressing you.
      </p>
      <Input
        id="display_name"
        label="Display name"
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        error={error ?? undefined}
        maxLength={60}
        required
      />
    </WizardShell>
  );
}
