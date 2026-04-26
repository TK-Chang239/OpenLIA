import { useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { FormField } from "../../components/primitives/FormField";
import { Input } from "../../components/primitives/Input";
import { PasswordInput } from "../../components/primitives/PasswordInput";
import { PasswordStrengthMeter } from "../../components/primitives/PasswordStrengthMeter";
import { setAdmin } from "../../api/setup";
import { useWizardField } from "../storage";

// Passwords are held in component state only and never passed to
// useWizardField, so they cannot reach sessionStorage.
interface PersistedAdmin {
  email: string;
  displayName: string;
}

const ADMIN_DEFAULTS: PersistedAdmin = { email: "", displayName: "" };

function parseAdmin(raw: unknown): PersistedAdmin {
  const r = (raw ?? {}) as Partial<PersistedAdmin>;
  return { email: r.email ?? "", displayName: r.displayName ?? "" };
}

export function AdminAccountStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [persisted, setPersisted] = useWizardField<PersistedAdmin>(
    "openlia.wizard.admin",
    ADMIN_DEFAULTS,
    parseAdmin,
  );
  const { email, displayName } = persisted;
  const setEmail = (value: string) =>
    setPersisted((prev) => ({ ...prev, email: value }));
  const setDisplayName = (value: string) =>
    setPersisted((prev) => ({ ...prev, displayName: value }));
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  const passwordValid = password.length >= 12;
  const passwordsMatch = password === confirm;
  const nameValid = displayName.trim().length >= 1;
  const canSubmit = emailValid && passwordValid && passwordsMatch && nameValid;

  const passwordError = password.length > 0 && !passwordValid ? "Must be at least 12 characters." : undefined;
  const confirmError = confirm.length > 0 && !passwordsMatch ? "Passwords don't match." : undefined;
  const emailError = email.length > 0 && !emailValid ? "Enter a valid email." : undefined;

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await setAdmin({ email, password, display_name: displayName.trim() });
      // Persist past Next; the wizard-wide clear runs after /setup/finish.
      // Password fields are component-only and remain blank on revisit.
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create admin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Admin account"
      stepIndex={1}
      totalSteps={6}
      footer={<WizardFooter onBack={onBack} onNext={onNext} nextDisabled={!canSubmit} loading={loading} />}
    >
      <p className="text-sm text-[--color-text-secondary] mb-6">
        You are creating the first administrator for this deployment. Additional users sign up on
        the login page per the policy you'll choose later.
      </p>
      <div className="flex flex-col gap-5">
        <Input
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={emailError}
          required
        />
        <div>
          <FormField id="password" label="Password" error={passwordError}>
            <PasswordInput
              id="password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              hasError={!!passwordError}
            />
          </FormField>
          <PasswordStrengthMeter value={password} />
        </div>
        <FormField id="confirm_password" label="Confirm password" error={confirmError}>
          <PasswordInput
            id="confirm_password"
            value={confirm}
            onChange={setConfirm}
            autoComplete="new-password"
            hasError={!!confirmError}
          />
        </FormField>
        <Input
          id="display_name"
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
          maxLength={60}
        />
      </div>
      {error ? <p className="text-sm text-[--color-feedback-error] mt-4">{error}</p> : null}
    </WizardShell>
  );
}
