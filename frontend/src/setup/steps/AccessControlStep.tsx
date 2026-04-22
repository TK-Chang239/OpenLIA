import { useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { setAccessControl } from "../../api/setup";

type Policy = "invite_only" | "closed";

export function AccessControlStep({
  onBack,
  onSaved,
}: {
  onBack: () => void;
  onSaved: () => void;
}) {
  const [policy, setPolicy] = useState<Policy>("invite_only");
  const [domains, setDomains] = useState("");
  const [host, setHost] = useState("0.0.0.0");
  const [port, setPort] = useState(8000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await setAccessControl({
        signup_policy: policy,
        allowed_domains: domains.trim() || undefined,
        bind_host: host,
        bind_port: port,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save access control.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell
      title="Access Control"
      stepIndex={4}
      totalSteps={6}
      footer={<WizardFooter onBack={onBack} onNext={onNext} loading={loading} />}
    >
      <fieldset className="mb-6">
        <legend className="text-sm font-medium text-[--color-text-primary] mb-2">
          Signup policy
        </legend>
        <label className="flex items-start gap-3 mb-2 cursor-pointer">
          <input
            type="radio"
            name="policy"
            aria-label="Invite-only"
            checked={policy === "invite_only"}
            onChange={() => setPolicy("invite_only")}
          />
          <span>
            <strong className="text-sm">Invite-only</strong>
            <p className="text-xs text-[--color-text-secondary]">
              Create invite links in Settings after setup. Share them with your team.
            </p>
          </span>
        </label>
        <label className="flex items-start gap-3 mb-2 cursor-pointer">
          <input
            type="radio"
            name="policy"
            aria-label="Closed"
            checked={policy === "closed"}
            onChange={() => setPolicy("closed")}
          />
          <span>
            <strong className="text-sm">Closed</strong>
            <p className="text-xs text-[--color-text-secondary]">
              No public registration; admin creates accounts manually via CLI.
            </p>
          </span>
        </label>
        <label className="flex items-start gap-3 mb-2 cursor-not-allowed opacity-60">
          <input type="radio" name="policy" aria-label="Open signup" disabled />
          <span>
            <strong className="text-sm">Open signup</strong>
            <p className="text-xs text-[--color-text-secondary]">Coming soon.</p>
          </span>
        </label>
      </fieldset>
      <label className="flex flex-col gap-1.5 mb-5">
        <span className="text-sm font-medium text-[--color-text-primary]">
          Allowed email domains (optional)
        </span>
        <input
          value={domains}
          onChange={(e) => setDomains(e.target.value)}
          placeholder="example.com, acme.com"
          className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
        />
      </label>
      <div className="grid grid-cols-2 gap-4 mb-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[--color-text-primary]">Bind host</span>
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-[--color-text-primary]">Bind port</span>
          <input
            type="number"
            min={1}
            max={65535}
            value={port}
            onChange={(e) => setPort(Number(e.target.value))}
            className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
        </label>
      </div>
      <p className="text-xs text-[--color-text-tertiary] mb-4">
        Changes to bind address and port take effect after you restart the server.
      </p>
      {error ? <p className="text-sm text-[--color-feedback-error]">{error}</p> : null}
    </WizardShell>
  );
}
