import { useState } from "react";
import type { ManualOverride, PanelStatus } from "../../api/panic-thermometer";

interface Props {
  current: ManualOverride | null;
  onSubmit: (override: ManualOverride | null) => void;
  onClose: () => void;
}

const STATUSES: PanelStatus[] = ["green", "amber", "red", "dark_red"];

export function ManualOverridePopover({
  current,
  onSubmit,
  onClose,
}: Props): JSX.Element {
  const [status, setStatus] = useState<PanelStatus>(current?.status ?? "amber");
  const [note, setNote] = useState<string>(current?.note ?? "");

  const submit = () => {
    onSubmit({
      status,
      note,
      set_at: new Date().toISOString(),
    });
    onClose();
  };

  return (
    <div
      role="dialog"
      data-testid="manual-override-popover"
      style={{
        padding: "1rem",
        background: "var(--color-bg-elevated)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      }}
    >
      <strong>Manual override</strong>
      <fieldset
        style={{ display: "flex", gap: "0.5rem", border: 0, padding: 0 }}
      >
        {STATUSES.map((s) => (
          <label key={s} style={{ display: "inline-flex", gap: "0.25rem" }}>
            <input
              type="radio"
              data-testid={`override-radio-${s}`}
              name="override-status"
              checked={status === s}
              onChange={() => setStatus(s)}
            />
            {s}
          </label>
        ))}
      </fieldset>
      <textarea
        data-testid="override-note"
        placeholder="Why are you overriding?"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={3}
      />
      <div style={{ display: "flex", gap: "0.25rem", justifyContent: "flex-end" }}>
        {current ? (
          <button
            type="button"
            data-testid="override-clear"
            onClick={() => {
              onSubmit(null);
              onClose();
            }}
          >
            Clear
          </button>
        ) : null}
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button type="button" data-testid="override-save" onClick={submit}>
          Save
        </button>
      </div>
    </div>
  );
}
