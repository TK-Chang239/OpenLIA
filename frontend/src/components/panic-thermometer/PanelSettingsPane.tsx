import { useState } from "react";
import {
  previewRuleset,
  type PanelConfig,
  type PtPreset,
  type RulesetPreviewResponse,
} from "../../api/panic-thermometer";
import { RuleEditor } from "./RuleEditor";

interface Props {
  config: PanelConfig;
  presets: PtPreset[];
  onChange: (next: PanelConfig) => void;
  onApplyPreset: (presetId: string) => void;
}

export function PanelSettingsPane({
  config,
  presets,
  onChange,
  onApplyPreset,
}: Props): JSX.Element {
  const [preview, setPreview] = useState<RulesetPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const updateParam = (key: string, value: string) => {
    const num = Number(value);
    onChange({
      ...config,
      params: {
        ...config.params,
        [key]: Number.isFinite(num) && value !== "" ? num : value,
      },
    });
  };

  const onTest = async () => {
    try {
      const res = await previewRuleset(config.panel_id, {
        rules: config.rules,
        params: config.params,
        streak_condition: config.streak_condition,
      });
      setPreview(res);
      setPreviewError(null);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : String(err));
    }
  };

  const panelPresets = presets.filter((p) => p.name.startsWith(`${config.panel_id}::`));

  return (
    <div
      data-testid={`panel-settings-${config.panel_id}`}
      style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}
    >
      <section>
        <strong>Parameters</strong>
        <table style={{ width: "100%" }}>
          <tbody>
            {Object.entries(config.params).map(([key, value]) => (
              <tr key={key}>
                <td style={{ padding: "2px 4px" }}>{key}</td>
                <td style={{ padding: "2px 4px" }}>
                  <input
                    data-testid={`param-${key}`}
                    type="text"
                    value={typeof value === "object" ? JSON.stringify(value) : String(value)}
                    onChange={(e) => updateParam(key, e.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <RuleEditor
        panel={config.panel_id}
        rules={config.rules}
        onChange={(rules) => onChange({ ...config, rules })}
      />
      <section>
        <strong>Presets</strong>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
          {panelPresets.map((p) => (
            <button
              key={p.id}
              type="button"
              data-testid={`preset-${p.name}`}
              onClick={() => onApplyPreset(p.id)}
            >
              {p.name}
            </button>
          ))}
        </div>
      </section>
      <section>
        <button type="button" onClick={onTest} data-testid="panel-test">
          Test ruleset
        </button>
        {previewError ? (
          <div role="alert" style={{ color: "var(--color-feedback-error)" }}>
            {previewError}
          </div>
        ) : null}
        {preview ? (
          <div data-testid="panel-preview" style={{ fontSize: "0.85rem" }}>
            Status: <strong>{preview.status}</strong> — {preview.label}
          </div>
        ) : null}
      </section>
    </div>
  );
}
