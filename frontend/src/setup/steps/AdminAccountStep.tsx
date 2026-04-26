import { useEffect, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { FormField } from "../../components/primitives/FormField";
import { Input } from "../../components/primitives/Input";
import { PasswordInput } from "../../components/primitives/PasswordInput";
import { PasswordStrengthMeter } from "../../components/primitives/PasswordStrengthMeter";
import { setAdmin } from "../../api/setup";
import { WIZARD_STORAGE_KEYS } from "../storage";

// Persist non-secret fields across back/forward navigation. Passwords are
// intentionally held in component state only — they are never written to
// sessionStorage.
const STORAGE_KEY: (typeof WIZARD_STORAGE_KEYS)[number] = "openlia.wizard.admin";

interface PersistedAdmin {
  email: string;
  displayName: string;
}

function loadPersisted(): PersistedAdmin {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { email: "", displayName: "" };
    const parsed = JSON.parse(raw) as Partial<PersistedAdmin>;
    return { email: parsed.email ?? "", displayName: parsed.displayName ?? "" };
  } catch {
    return { email: "", displayName: "" };
  }
}

export function AdminAccountStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const persisted = loadPersisted();
  const [email, setEmail] = useState(persisted.email);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [displayName, setDisplayName] = useState(persisted.displayName);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ email, displayName }));
    } catch {
      /* ignore */
    }
  }, [email, displayName]);

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
