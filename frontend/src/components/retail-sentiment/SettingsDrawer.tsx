import { useState } from "react";
import { useTranslation } from "react-i18next";

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

const FIELD_INPUT =
  "h-8 px-2.5 rounded-md border bg-[--color-bg-input] text-[12.5px] font-mono tabular-nums focus:outline-none focus:border-[--color-accent-primary]";

export function SettingsDrawer({ open, initial, onClose, onSave }: Props) {
  const { t } = useTranslation();
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
    <>
      <button
        type="button"
        onClick={onClose}
        aria-label={t("retail_sentiment.settings_drawer.close_aria")}
        className="fixed inset-0 z-30 bg-black/40"
      />
      <aside
        role="dialog"
        aria-label={t("retail_sentiment.settings_drawer.aria")}
        data-testid="settings-drawer"
        className="fixed inset-y-0 right-0 z-40 flex w-[420px] max-w-full flex-col border-l shadow-2xl"
        style={{
          background: "var(--color-bg-elevated)",
          borderColor: "var(--color-border-subtle)",
        }}
      >
        <header
          className="flex items-center justify-between px-5"
          style={{
            height: 52,
            borderBottom: "1px solid var(--color-border-subtle)",
          }}
        >
          <span
            className="font-mono"
            style={{
              fontSize: 10,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--color-text-tertiary)",
            }}
          >
            {t("retail_sentiment.settings_drawer.header")}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("retail_sentiment.settings_drawer.close")}
            className="inline-flex items-center h-8 px-3 rounded-md border text-[12px] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            style={{
              borderColor: "var(--color-border-secondary)",
              color: "var(--color-text-secondary)",
            }}
          >
            {t("retail_sentiment.settings_drawer.close")}
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          <section className="space-y-3">
            <h3
              className="m-0 rs-mono-label"
              style={{ color: "var(--color-text-primary)" }}
            >
              {t("retail_sentiment.settings_drawer.thresholds")}
            </h3>
            <label className="grid gap-1">
              <span className="rs-mono-label">
                {t("retail_sentiment.settings_drawer.spike_z")}
              </span>
              <input
                type="number"
                step="0.1"
                value={state.thresholds.spike_z}
                onChange={(e) => setSpikeZ(Number(e.target.value))}
                className={FIELD_INPUT}
                style={{ borderColor: "var(--color-border-secondary)" }}
              />
            </label>
            <label className="grid gap-1">
              <span className="rs-mono-label">
                {t("retail_sentiment.settings_drawer.divergence")}
              </span>
              <input
                type="number"
                step="0.1"
                value={state.thresholds.divergence}
                onChange={(e) => setDivergence(Number(e.target.value))}
                className={FIELD_INPUT}
                style={{ borderColor: "var(--color-border-secondary)" }}
              />
            </label>
          </section>
          <section className="space-y-3">
            <h3
              className="m-0 rs-mono-label"
              style={{ color: "var(--color-text-primary)" }}
            >
              {t("retail_sentiment.settings_drawer.weights")}
            </h3>
            {Object.entries(state.cross_source_weights).map(([key, val]) => (
              <label key={key} className="grid gap-1">
                <span className="rs-mono-label">{key}</span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step="0.05"
                  value={val}
                  onChange={(e) => setWeight(key, Number(e.target.value))}
                  className={FIELD_INPUT}
                  style={{ borderColor: "var(--color-border-secondary)" }}
                />
              </label>
            ))}
          </section>
        </div>
        <footer
          className="px-5 py-3 flex items-center justify-end gap-2"
          style={{ borderTop: "1px solid var(--color-border-subtle)" }}
        >
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center h-8 px-3 rounded-md border text-[12px]"
            style={{
              borderColor: "var(--color-border-secondary)",
              color: "var(--color-text-secondary)",
            }}
          >
            {t("retail_sentiment.settings_drawer.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={busy}
            className="inline-flex items-center h-8 px-3 rounded-md text-[12px] font-medium disabled:opacity-60"
            style={{
              background: "var(--color-accent-primary)",
              color: "var(--color-accent-on)",
            }}
          >
            {busy
              ? t("retail_sentiment.settings_drawer.saving")
              : t("retail_sentiment.settings_drawer.save")}
          </button>
        </footer>
      </aside>
    </>
  );
}
