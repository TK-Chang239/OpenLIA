import { useEffect, useState } from "react";

import {
  createHolding,
  updateHolding,
  type HoldingInput,
  type HoldingPatch,
  type PortfolioHolding,
} from "../api/portfolio";
import { GroupCombobox } from "./GroupCombobox";
import type { Market } from "./marketTypes";
import { MARKET_CURRENCIES } from "./marketTypes";
import { normalizeTicker } from "./tickerNormalize";

function parseDecimal(raw: string): number | null {
  const t = raw.trim();
  if (!t) return null;
  const n = Number(t);
  if (!Number.isFinite(n)) return null;
  if (n <= 0) return null;
  return n;
}

function formatDecimal(n: number): string {
  if (!Number.isFinite(n)) return "";
  const fixed = n.toFixed(4);
  const trimmed = fixed.replace(/\.?0+$/, "");
  return trimmed === "" || trimmed === "-" ? "0" : trimmed;
}

interface BlendInput {
  action: "buy" | "sell";
  currentShares: number | null;
  currentCostBasis: number | null;
  qty: number;
  price: number;
}

interface BlendOutput {
  newShares: number;
  newCostBasis: number | null;
}

function computeBlend(input: BlendInput): BlendOutput {
  const { action, currentShares, currentCostBasis, qty, price } = input;
  if (action === "buy") {
    const s0 = currentShares ?? 0;
    const newShares = s0 + qty;
    if (s0 === 0 || currentCostBasis === null) {
      return { newShares, newCostBasis: price };
    }
    const newCostBasis = (s0 * currentCostBasis + qty * price) / newShares;
    return { newShares, newCostBasis };
  }
  const s0 = currentShares ?? 0;
  return { newShares: s0 - qty, newCostBasis: currentCostBasis };
}

export const __test = { parseDecimal, formatDecimal, computeBlend };

export interface AddEditDrawerProps {
  readonly open: boolean;
  readonly mode: "create" | "edit";
  readonly initial?: PortfolioHolding | null;
  readonly groups?: readonly string[];
  readonly market: Market;
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
  added_at_date: string;
}

function todayLocalIso(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

const blank: FormState = {
  ticker: "",
  shares: "",
  cost_basis: "",
  currency: "USD",
  notes: "",
  group: null,
  added_at_date: "",
};

export function AddEditDrawer({
  open,
  mode,
  initial,
  groups = [],
  market,
  onCreateGroup,
  onClose,
  onSaved,
}: AddEditDrawerProps): JSX.Element | null {
  const [form, setForm] = useState<FormState>(blank);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (open && initial) {
      setForm({
        ticker: initial.ticker,
        shares: initial.shares ?? "",
        cost_basis: initial.cost_basis ?? "",
        currency: initial.currency,
        notes: initial.notes_text ?? "",
        group: initial.groups[0] ?? null,
        added_at_date: "",
      });
    } else if (open) {
      setForm({
        ...blank,
        currency: MARKET_CURRENCIES[market],
        added_at_date: todayLocalIso(),
      });
    }
    setError(null);
    if (open) setClosing(false);
  }, [open, initial, market]);

  const beginClose = () => {
    if (closing) return;
    setClosing(true);
  };

  const onFormAnimationEnd = (e: React.AnimationEvent<HTMLFormElement>) => {
    if (closing && e.animationName === "ol-drawer-out") {
      onClose();
      setClosing(false);
    }
  };

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const groupsArray = form.group ? [form.group] : [];
      if (mode === "create") {
        if (!form.shares.trim()) {
          setError("Shares is required");
          setSubmitting(false);
          return;
        }
        const normalized = normalizeTicker(form.ticker, market);
        if (!normalized.ok || !normalized.ticker) {
          setError(normalized.error ?? "Invalid ticker");
          setSubmitting(false);
          return;
        }
        const dateStr = form.added_at_date.trim();
        if (dateStr) {
          if (!DATE_REGEX.test(dateStr)) {
            setError("Date must be YYYY-MM-DD");
            setSubmitting(false);
            return;
          }
          if (dateStr > todayLocalIso()) {
            setError("Date cannot be in the future");
            setSubmitting(false);
            return;
          }
        }
        const input: HoldingInput = {
          ticker: normalized.ticker,
          shares: form.shares,
          cost_basis: form.cost_basis || null,
          currency: form.currency || MARKET_CURRENCIES[market],
          notes: form.notes || null,
          groups: groupsArray,
          added_at_date: dateStr || null,
        };
        const created = await createHolding(input, market);
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
      beginClose();
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
      aria-label={mode === "create" ? "Add position" : "Edit position"}
      className="fixed inset-0 z-40 flex justify-end"
      data-testid="add-edit-drawer"
    >
      <button
        type="button"
        aria-label="Close drawer"
        className={`absolute inset-0 cursor-default bg-black/30 backdrop-blur-[2px] transition-opacity duration-200 ${closing ? "opacity-0" : "opacity-100"}`}
        onClick={beginClose}
      />
      <form
        onSubmit={submit}
        onAnimationEnd={onFormAnimationEnd}
        className={`relative ml-auto flex h-full w-[400px] flex-col overflow-y-auto border-l border-[--color-border-subtle] bg-[--color-bg-elevated] p-6 shadow-[-12px_0_40px_rgba(0,0,0,0.16)] ${closing ? "motion-safe:animate-[ol-drawer-out_200ms_ease-in_forwards]" : "motion-safe:animate-[ol-drawer-in_240ms_ease-out]"}`}
      >
        <h2 className="text-lg font-semibold mb-4">
          {mode === "create" ? "Add Position" : "Edit Position"}
        </h2>

        <label className="block text-xs text-[--color-text-tertiary]">
          Ticker
          <input
            value={form.ticker}
            disabled={mode === "edit"}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-ticker"
            placeholder={market === "tw" ? "e.g. 2330" : "e.g. AAPL"}
          />
          {mode === "create" ? (
            <span className="mt-1 block text-[10px] leading-tight text-[--color-text-tertiary]">
              {market === "tw"
                ? "TW portfolio — 3-6 digit code, auto-suffixed with .TW."
                : "US portfolio — bare ticker (AAPL); reject .TW symbols."}
            </span>
          ) : null}
        </label>

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Shares <span className="text-[--color-feedback-error]">*</span>
          <input
            value={form.shares ?? ""}
            onChange={(e) => setForm({ ...form, shares: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-shares"
            placeholder="e.g. 100"
          />
        </label>

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Cost Basis (per share)
          <input
            value={form.cost_basis ?? ""}
            onChange={(e) => setForm({ ...form, cost_basis: e.target.value })}
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            data-testid="drawer-cost"
            placeholder="optional"
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

        {mode === "create" ? (
          <label className="block text-xs text-[--color-text-tertiary] mt-3">
            Date Acquired
            <input
              value={form.added_at_date}
              onChange={(e) =>
                setForm({ ...form, added_at_date: e.target.value })
              }
              className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
              data-testid="drawer-added-at"
              placeholder="YYYY-MM-DD"
              maxLength={10}
            />
            <span className="mt-1 block text-[10px] leading-tight text-[--color-text-tertiary]">
              Defaults to today. Past dates included in historical NAV from that
              day forward.
            </span>
          </label>
        ) : null}

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
            onClick={beginClose}
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
