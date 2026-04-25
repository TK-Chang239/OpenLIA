import { useState } from "react";

interface SettingsState {
  thresholds: {
    spike_z: number;
    divergence: number;
  };
  cross_source_weights: Record<string, number>;
}

interface Props {
  open: boolean;
  initial?: SettingsState;
  onClose: () => void;
  onSave: (state: SettingsState) => Promise<void> | void;
}

const DEFAULTS: SettingsState = {
  thresholds: { spike_z: 2.0, divergence: 1.0 },
  cross_source_weights: {
    financial_provider: 0.4,
    social_media: 0.35,
    cross_platform: 0.25,
  },
};

export function SettingsDrawer({ open, initial, onClose, onSave }: Props) {
  const [state, setState] = useState<SettingsState>(initial ?? DEFAULTS);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const setSpikeZ = (v: number) =>
    setState((s) => ({
      ...s,
      thresholds: { ...s.thresholds, spike_z: v },
    }));
  const setDivergence = (v: number) =>
    setState((s) => ({
      ...s,
      thresholds: { ...s.thresholds, divergence: v },
    }));
  const setWeight = (key: string, v: number) =>
    setState((s) => ({
      ...s,
      cross_source_weights: { ...s.cross_source_weights, [key]: v },
    }));

  const submit = async () => {
    setBusy(true);
    try {
      await onSave(state);
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="Retail Sentiment settings"
      data-testid="settings-drawer"
      className="fixed inset-y-0 right-0 z-40 flex w-[400px] max-w-full flex-col border-l border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-2xl"
    >
      <header className="flex items-center justify-between border-b border-[--color-border-subtle] px-4 py-3">
        <h2 className="text-sm font-semibold">Settings</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close settings"
          className="rounded-md border border-[--color-border-secondary] px-2 py-1 text-xs"
        >
          Close
        </button>
      </header>
      <div className="space-y-4 overflow-y-auto p-4 text-sm">
        <section>
          <h3 className="mb-2 text-xs uppercase text-[--color-text-secondary]">
            Thresholds
          </h3>
          <label className="grid gap-1">
            Spike z-score
            <input
              type="number"
              step="0.1"
              value={state.thresholds.spike_z}
              onChange={(e) => setSpikeZ(Number(e.target.value))}
              className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1"
            />
          </label>
          <label className="mt-2 grid gap-1">
            Divergence threshold
            <input
              type="number"
              step="0.1"
              value={state.thresholds.divergence}
              onChange={(e) => setDivergence(Number(e.target.value))}
              className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1"
            />
          </label>
        </section>
        <section>
          <h3 className="mb-2 text-xs uppercase text-[--color-text-secondary]">
            Cross-source weights
          </h3>
          {Object.entries(state.cross_source_weights).map(([key, val]) => (
            <label key={key} className="grid gap-1">
              {key}
              <input
                type="number"
                min={0}
                max={1}
                step="0.05"
                value={val}
                onChange={(e) => setWeight(key, Number(e.target.value))}
                className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1"
              />
            </label>
          ))}
        </section>
      </div>
      <footer className="border-t border-[--color-border-subtle] p-3 text-right">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={busy}
          className="rounded-md bg-[--color-accent-primary] px-3 py-1 text-xs text-[--color-accent-on] disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </footer>
    </div>
  );
}
