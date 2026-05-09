import { useEffect, useState } from "react";

import {
  createHolding,
  updateHolding,
  type HoldingInput,
  type HoldingPatch,
  type PortfolioHolding,
} from "../api/portfolio";
import { GroupCombobox } from "./GroupCombobox";

export interface AddEditDrawerProps {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly initial?: PortfolioHolding | null;
  readonly groups?: readonly string[];
  readonly onCreateGroup?: (name: string) => Promise<void> | void;
  readonly onClose: () => void;
  readonly onSaved: (h: PortfolioHolding) => void;
}

interface FormState {
  ticker: string;
  shares: string;
  cost_basis: string;
  currency: string;
  notes: string;
  group: string | null;
}

const blank: FormState = {
  ticker: "",
  shares: "",
  cost_basis: "",
  currency: "USD",
  notes: "",
  group: null,
};

export function AddEditDrawer({
  open,
  mode,
  initial,
  groups = [],
  onCreateGroup,
  onClose,
  onSaved,
}: AddEditDrawerProps): JSX.Element | null {
  const [form, setForm] = useState<FormState>(blank);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && initial) {
      setForm({
        ticker: initial.ticker,
        shares: initial.shares ?? "",
        cost_basis: initial.cost_basis ?? "",
        currency: initial.currency,
        notes: initial.notes_text ?? "",
        group: initial.groups[0] ?? null,
      });
    } else if (open) {
      setForm(blank);
    }
    setError(null);
  }, [open, initial]);

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const groupsArray = form.group ? [form.group] : [];
      if (mode === "create") {
        const input: HoldingInput = {
          ticker: form.ticker.trim(),
          shares: form.shares || null,
          cost_basis: form.cost_basis || null,
          currency: form.currency || "USD",
          notes: form.notes || null,
          groups: groupsArray,
        };
        const created = await createHolding(input);
        onSaved(created);
      } else if (initial) {
        const patch: HoldingPatch = {
          shares: form.shares || null,
          cost_basis: form.cost_basis || null,
          currency: form.currency,
          notes: form.notes || null,
          groups: groupsArray,
        };
        const updated = await updateHolding(initial.id, patch);
        onSaved(updated);
      }
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={mode === "create" ? "Add holding" : "Edit holding"}
      className="fixed inset-0 z-40 flex justify-end"
      data-testid="add-edit-drawer"
    >
      <button
        type="button"
        aria-label="Close drawer"
        className="absolute inset-0 cursor-default bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <form
        onSubmit={submit}
        className="relative ml-auto flex h-full w-[400px] flex-col overflow-y-auto border-l border-[--color-border-subtle] bg-[--color-bg-elevated] p-6 shadow-[-12px_0_40px_rgba(0,0,0,0.16)] motion-safe:animate-[ol-drawer-in_240ms_ease-out]"
      >
        <h2 className="text-lg font-semibold mb-4">
          {mode === "create" ? "Add holding" : "Edit holding"}
        </h2>

        <label className="block text-xs text-[--color-text-tertiary]">
          Ticker
          <input
            value={form.ticker}
            disabled={mode === "edit"}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-ticker"
          />
        </label>

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Shares
          <input
            value={form.shares ?? ""}
            onChange={(e) => setForm({ ...form, shares: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-shares"
          />
        </label>

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Cost Basis
          <input
            value={form.cost_basis ?? ""}
            onChange={(e) => setForm({ ...form, cost_basis: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-cost"
          />
        </label>

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Currency
          <input
            value={form.currency ?? "USD"}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-currency"
          />
        </label>

        <div className="block text-xs text-[--color-text-tertiary] mt-3">
          Group
          <div className="mt-1" data-testid="drawer-group">
            <GroupCombobox
              value={form.group}
              groups={[...groups]}
              onChange={(next) => setForm({ ...form, group: next })}
              onCreateGroup={onCreateGroup}
              placeholder="No group"
            />
          </div>
          <p className="mt-1 text-[10px] leading-tight text-[--color-text-tertiary]">
            Each holding belongs to one group; allocations sum cleanly.
          </p>
        </div>

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Notes
          <textarea
            value={form.notes ?? ""}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            rows={3}
          />
        </label>

        {error ? (
          <p className="text-xs text-[--color-feedback-error] mt-3">{error}</p>
        ) : null}

        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1 text-sm rounded-[--radius-sm] border border-[--color-border-subtle]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !form.ticker.trim()}
            className="px-3 py-1 text-sm rounded-[--radius-sm] bg-[--color-accent-primary] text-white disabled:opacity-40"
            data-testid="drawer-save"
          >
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
