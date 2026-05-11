# Edit Position — Adjust Shares (Buy/Sell) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Buy/Sell "Adjust position" section to the Edit Position drawer that computes new shares + blended cost basis and writes them into the existing raw form fields, with no backend changes.

**Architecture:** All work happens inside `frontend/src/portfolio/AddEditDrawer.tsx`. A new private `AdjustPositionSection` component owns its own sub-form state (action, qty, price) and calls a parent-supplied `onApply(newShares, newCostBasis)` callback. The parent drawer writes those values into its existing `form.shares` / `form.cost_basis` state. Save uses the existing `updateHolding(id, HoldingPatch)` flow unchanged. Math helpers (`computeBlend`, `formatDecimal`) are pure functions colocated in the same file.

**Tech Stack:** React 18, TypeScript, Vitest + React Testing Library, Tailwind utility classes already in use across the file.

Spec: `docs/superpowers/specs/2026-05-11-edit-position-adjust-shares-design.md`

---

## File Structure

- Modify: `frontend/src/portfolio/AddEditDrawer.tsx` — add `AdjustPositionSection`, helpers `parseDecimal`, `formatDecimal`, `computeBlend`, wire into edit-mode render.
- Modify: `frontend/src/portfolio/AddEditDrawer.test.tsx` — add tests for the new section.

No other files change.

---

### Task 1: Math + parse helpers (pure, TDD)

**Files:**
- Modify: `frontend/src/portfolio/AddEditDrawer.tsx` (add private helpers near top of file)
- Modify: `frontend/src/portfolio/AddEditDrawer.test.tsx` (add a new `describe` block)

These helpers do the decimal parsing and the buy-blend math. They are not exported; tests reach them by exporting them from the file. Export them with an `__test` marker so the public API of the module stays unchanged.

- [ ] **Step 1.1: Write failing tests for `parseDecimal`, `formatDecimal`, `computeBlend`**

Add to `frontend/src/portfolio/AddEditDrawer.test.tsx` (append after existing `describe`):

```tsx
import { __test } from "./AddEditDrawer";

describe("AddEditDrawer helpers", () => {
  const { parseDecimal, formatDecimal, computeBlend } = __test;

  describe("parseDecimal", () => {
    it("returns null for empty / whitespace", () => {
      expect(parseDecimal("")).toBeNull();
      expect(parseDecimal("   ")).toBeNull();
    });

    it("returns null for non-numeric", () => {
      expect(parseDecimal("abc")).toBeNull();
    });

    it("parses positive decimals", () => {
      expect(parseDecimal("128.40")).toBe(128.4);
      expect(parseDecimal("0.5")).toBe(0.5);
    });

    it("returns null for negative or zero (parseDecimal is for inputs that must be > 0 when provided)", () => {
      expect(parseDecimal("-1")).toBeNull();
      expect(parseDecimal("0")).toBeNull();
    });
  });

  describe("formatDecimal", () => {
    it("trims trailing zeros up to 4 dp", () => {
      expect(formatDecimal(110)).toBe("110");
      expect(formatDecimal(129.5454545)).toBe("129.5455");
      expect(formatDecimal(130.4)).toBe("130.4");
      expect(formatDecimal(130.4000)).toBe("130.4");
    });

    it("formats whole numbers without decimals", () => {
      expect(formatDecimal(0)).toBe("0");
    });
  });

  describe("computeBlend (Buy)", () => {
    it("blends weighted avg cost basis", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: 100,
        currentCostBasis: 128,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(110);
      expect(newCostBasis).toBeCloseTo((100 * 128 + 10 * 145) / 110, 6);
    });

    it("sets cost basis = price when current cost basis is null", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: 100,
        currentCostBasis: null,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(110);
      expect(newCostBasis).toBe(145);
    });

    it("sets shares=qty, cost=price when current shares is null", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: null,
        currentCostBasis: null,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(10);
      expect(newCostBasis).toBe(145);
    });

    it("sets shares=qty, cost=price when current shares is 0", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "buy",
        currentShares: 0,
        currentCostBasis: 99,
        qty: 10,
        price: 145,
      });
      expect(newShares).toBe(10);
      expect(newCostBasis).toBe(145);
    });
  });

  describe("computeBlend (Sell)", () => {
    it("decrements shares and leaves cost basis unchanged", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "sell",
        currentShares: 100,
        currentCostBasis: 128,
        qty: 25,
        price: 135,
      });
      expect(newShares).toBe(75);
      expect(newCostBasis).toBe(128);
    });

    it("keeps cost basis null when it was null", () => {
      const { newShares, newCostBasis } = computeBlend({
        action: "sell",
        currentShares: 100,
        currentCostBasis: null,
        qty: 25,
        price: 135,
      });
      expect(newShares).toBe(75);
      expect(newCostBasis).toBeNull();
    });
  });
});
```

- [ ] **Step 1.2: Run tests to verify failure**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx`
Expected: tests in the new `describe("AddEditDrawer helpers")` block fail with "Cannot read property of undefined" (because `__test` doesn't exist yet).

- [ ] **Step 1.3: Implement helpers + export them under `__test`**

In `frontend/src/portfolio/AddEditDrawer.tsx`, just above `export interface AddEditDrawerProps`, add:

```tsx
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
  return fixed.replace(/\.?0+$/, "");
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
```

- [ ] **Step 1.4: Run tests to verify pass**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx`
Expected: helper tests all PASS. Existing AddEditDrawer tests still PASS.

- [ ] **Step 1.5: Commit**

```bash
git add frontend/src/portfolio/AddEditDrawer.tsx frontend/src/portfolio/AddEditDrawer.test.tsx
git commit -m "$(cat <<'EOF'
feat(portfolio): blend helpers for adjust-shares (parseDecimal, formatDecimal, computeBlend)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: AdjustPositionSection component (renders in edit mode, no apply yet)

**Files:**
- Modify: `frontend/src/portfolio/AddEditDrawer.tsx` (add private component, render in edit mode)
- Modify: `frontend/src/portfolio/AddEditDrawer.test.tsx` (add presence test)

- [ ] **Step 2.1: Write failing test — section is present in edit mode, absent in create mode**

Append to `describe("AddEditDrawer", ...)`:

```tsx
it("renders AdjustPositionSection in edit mode", () => {
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={sample}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );
  expect(screen.getByTestId("adjust-section")).toBeInTheDocument();
});

it("does not render AdjustPositionSection in create mode", () => {
  render(
    <AddEditDrawer
      open
      mode="create"
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );
  expect(screen.queryByTestId("adjust-section")).toBeNull();
});
```

- [ ] **Step 2.2: Run tests to verify failure**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx`
Expected: 2 new tests FAIL (`getByTestId("adjust-section")` not found).

- [ ] **Step 2.3: Implement `AdjustPositionSection` (skeleton, no Apply logic yet)**

Add at the bottom of `frontend/src/portfolio/AddEditDrawer.tsx`:

```tsx
type AdjustAction = "buy" | "sell";

interface AdjustPositionSectionProps {
  readonly currentShares: number | null;
  readonly currentCostBasis: number | null;
  readonly onApply: (newShares: string, newCostBasis: string | null) => void;
}

function AdjustPositionSection({
  currentShares,
  currentCostBasis,
  onApply,
}: AdjustPositionSectionProps): JSX.Element {
  const [action, setAction] = useState<AdjustAction>("buy");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  const qtyNum = parseDecimal(qty);
  const priceNum = parseDecimal(price);
  const canPreview = qtyNum !== null && priceNum !== null;

  let previewText: string | null = null;
  let previewError: string | null = null;
  if (canPreview) {
    if (action === "sell" && currentShares === null) {
      previewError = "Set current shares first.";
    } else if (action === "sell" && qtyNum! > (currentShares ?? 0)) {
      previewError = `Cannot sell more than current shares (${formatDecimal(currentShares ?? 0)}).`;
    } else {
      const { newShares, newCostBasis } = computeBlend({
        action,
        currentShares,
        currentCostBasis,
        qty: qtyNum!,
        price: priceNum!,
      });
      const costPart =
        newCostBasis === null ? "" : ` @ avg $${formatDecimal(newCostBasis)}`;
      previewText = `-> ${formatDecimal(newShares)} shares${costPart}`;
    }
  }

  const onApplyClick = () => {
    setError(null);
    if (qtyNum === null) {
      setError("Enter a positive share count.");
      return;
    }
    if (priceNum === null) {
      setError("Enter a positive price.");
      return;
    }
    if (action === "sell" && currentShares === null) {
      setError("Set current shares first.");
      return;
    }
    if (action === "sell" && qtyNum > (currentShares ?? 0)) {
      setError(
        `Cannot sell more than current shares (${formatDecimal(currentShares ?? 0)}).`,
      );
      return;
    }
    const { newShares, newCostBasis } = computeBlend({
      action,
      currentShares,
      currentCostBasis,
      qty: qtyNum,
      price: priceNum,
    });
    onApply(
      formatDecimal(newShares),
      newCostBasis === null ? null : formatDecimal(newCostBasis),
    );
    setQty("");
    setPrice("");
  };

  const applyDisabled = qtyNum === null || priceNum === null;

  return (
    <div
      data-testid="adjust-section"
      className="mt-3 rounded-[--radius-sm] border border-[--color-border-subtle] p-3"
    >
      <div className="text-xs font-semibold text-[--color-text-secondary] mb-2">
        Adjust position
      </div>
      <div
        role="tablist"
        aria-label="Adjustment action"
        className="inline-flex rounded-[--radius-sm] border border-[--color-border-subtle] overflow-hidden mb-2"
      >
        <button
          type="button"
          role="tab"
          aria-selected={action === "buy"}
          data-testid="adjust-buy"
          onClick={() => setAction("buy")}
          className={`px-3 py-1 text-xs ${action === "buy" ? "bg-[--color-accent-primary] text-white" : "bg-transparent text-[--color-text-secondary]"}`}
        >
          Buy
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={action === "sell"}
          data-testid="adjust-sell"
          onClick={() => setAction("sell")}
          className={`px-3 py-1 text-xs ${action === "sell" ? "bg-[--color-accent-primary] text-white" : "bg-transparent text-[--color-text-secondary]"}`}
        >
          Sell
        </button>
      </div>
      <div className="flex gap-2 items-end">
        <label className="block text-xs text-[--color-text-tertiary] flex-1">
          Shares
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            data-testid="adjust-qty"
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            placeholder="e.g. 10"
          />
        </label>
        <label className="block text-xs text-[--color-text-tertiary] flex-1">
          Price per share
          <input
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            data-testid="adjust-price"
            className="block w-full mt-1 px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
            placeholder="e.g. 145.00"
          />
        </label>
        <button
          type="button"
          onClick={onApplyClick}
          disabled={applyDisabled}
          data-testid="adjust-apply"
          className="px-3 py-1 text-sm rounded-[--radius-sm] border border-[--color-border-subtle] disabled:opacity-40"
        >
          Apply
        </button>
      </div>
      <div className="mt-2 text-[11px] min-h-[14px]" data-testid="adjust-preview">
        {error ? (
          <span className="text-[--color-feedback-error]">{error}</span>
        ) : previewError ? (
          <span className="text-[--color-feedback-error]">{previewError}</span>
        ) : previewText ? (
          <span className="text-[--color-text-tertiary]">{previewText}</span>
        ) : null}
      </div>
    </div>
  );
}
```

Then wire it into the edit-mode render path. In the form body, find the `Shares` label block (currently at lines around 210-219) and insert the section *immediately before* it, gated on edit mode. Replace:

```tsx
        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Shares <span className="text-[--color-feedback-error]">*</span>
```

with:

```tsx
        {mode === "edit" && initial ? (
          <AdjustPositionSection
            currentShares={parseDecimal(form.shares)}
            currentCostBasis={parseDecimal(form.cost_basis)}
            onApply={(newShares, newCostBasis) =>
              setForm((f) => ({
                ...f,
                shares: newShares,
                cost_basis: newCostBasis ?? "",
              }))
            }
          />
        ) : null}

        <label className="block text-xs text-[--color-text-tertiary] mt-3">
          Shares <span className="text-[--color-feedback-error]">*</span>
```

- [ ] **Step 2.4: Run tests to verify pass**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx`
Expected: all existing tests + 2 new presence tests PASS.

- [ ] **Step 2.5: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 2.6: Commit**

```bash
git add frontend/src/portfolio/AddEditDrawer.tsx frontend/src/portfolio/AddEditDrawer.test.tsx
git commit -m "$(cat <<'EOF'
feat(portfolio): AdjustPositionSection component scaffold in edit drawer

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Buy applies and updates raw fields

**Files:**
- Modify: `frontend/src/portfolio/AddEditDrawer.test.tsx`

- [ ] **Step 3.1: Write failing test — Buy 10 @ $145 on 10 sh @ $150 yields 20 sh @ $147.50**

Append to `describe("AddEditDrawer", ...)`:

```tsx
it("Buy: blends cost basis and updates raw fields", () => {
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={sample}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );

  const sharesField = screen.getByTestId("drawer-shares") as HTMLInputElement;
  const costField = screen.getByTestId("drawer-cost") as HTMLInputElement;
  expect(sharesField.value).toBe("10");
  expect(costField.value).toBe("150");

  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "10" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "145" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  expect(sharesField.value).toBe("20");
  // (10*150 + 10*145) / 20 = 147.5
  expect(costField.value).toBe("147.5");

  // qty/price cleared
  expect((screen.getByTestId("adjust-qty") as HTMLInputElement).value).toBe("");
  expect((screen.getByTestId("adjust-price") as HTMLInputElement).value).toBe(
    "",
  );
});
```

- [ ] **Step 3.2: Run test to verify pass**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx -t "Buy: blends cost basis"`
Expected: PASS (apply wiring was implemented in Task 2; this test locks the behavior).

- [ ] **Step 3.3: Commit**

```bash
git add frontend/src/portfolio/AddEditDrawer.test.tsx
git commit -m "$(cat <<'EOF'
test(portfolio): cover Buy adjust path in edit drawer

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Sell applies and Sell validation

**Files:**
- Modify: `frontend/src/portfolio/AddEditDrawer.test.tsx`

- [ ] **Step 4.1: Write failing tests — Sell happy path + over-qty block + null-shares block**

Append to `describe("AddEditDrawer", ...)`:

```tsx
it("Sell: decrements shares, cost basis unchanged", () => {
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={sample}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );
  fireEvent.click(screen.getByTestId("adjust-sell"));
  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "200" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  expect((screen.getByTestId("drawer-shares") as HTMLInputElement).value).toBe(
    "7",
  );
  expect((screen.getByTestId("drawer-cost") as HTMLInputElement).value).toBe(
    "150",
  );
});

it("Sell: blocked when qty exceeds current shares", () => {
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={sample}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );
  fireEvent.click(screen.getByTestId("adjust-sell"));
  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "999" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "200" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  // raw fields unchanged
  expect((screen.getByTestId("drawer-shares") as HTMLInputElement).value).toBe(
    "10",
  );
  expect(screen.getByTestId("adjust-preview").textContent).toMatch(
    /Cannot sell more than current shares/,
  );
});

it("Sell: blocked when current shares is null", () => {
  const noShares: api.PortfolioHolding = { ...sample, shares: null };
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={noShares}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );
  fireEvent.click(screen.getByTestId("adjust-sell"));
  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "200" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  expect((screen.getByTestId("drawer-shares") as HTMLInputElement).value).toBe(
    "",
  );
  expect(screen.getByTestId("adjust-preview").textContent).toMatch(
    /Set current shares first/,
  );
});
```

(`api.PortfolioHolding.shares` is typed `string | null` in the api module — confirm by reading `frontend/src/api/portfolio.ts` before adjusting the cast.)

- [ ] **Step 4.2: Run tests to verify pass**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx -t "Sell"`
Expected: 3 PASS (the validation paths were already implemented in Task 2; these tests lock the behavior).

- [ ] **Step 4.3: Commit**

```bash
git add frontend/src/portfolio/AddEditDrawer.test.tsx
git commit -m "$(cat <<'EOF'
test(portfolio): cover Sell adjust path + validation in edit drawer

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Stacked applies + null cost basis Buy

**Files:**
- Modify: `frontend/src/portfolio/AddEditDrawer.test.tsx`

- [ ] **Step 5.1: Write failing tests — stacked applies blend correctly, Buy with null cost basis sets cost=price**

Append to `describe("AddEditDrawer", ...)`:

```tsx
it("Buy: stacks two applies, blending each time", () => {
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={sample}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );

  // First apply: buy 10 @ 145 -> (10*150 + 10*145)/20 = 147.5
  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "10" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "145" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  // Second apply: buy 5 @ 160 -> (20*147.5 + 5*160)/25 = 150
  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "5" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "160" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  expect((screen.getByTestId("drawer-shares") as HTMLInputElement).value).toBe(
    "25",
  );
  expect((screen.getByTestId("drawer-cost") as HTMLInputElement).value).toBe(
    "150",
  );
});

it("Buy: with null current cost basis sets cost = price", () => {
  const noCost: api.PortfolioHolding = { ...sample, cost_basis: null };
  render(
    <AddEditDrawer
      open
      mode="edit"
      initial={noCost}
      market="us"
      onClose={() => {}}
      onSaved={() => {}}
    />,
  );

  fireEvent.change(screen.getByTestId("adjust-qty"), {
    target: { value: "5" },
  });
  fireEvent.change(screen.getByTestId("adjust-price"), {
    target: { value: "120" },
  });
  fireEvent.click(screen.getByTestId("adjust-apply"));

  expect((screen.getByTestId("drawer-shares") as HTMLInputElement).value).toBe(
    "15",
  );
  expect((screen.getByTestId("drawer-cost") as HTMLInputElement).value).toBe(
    "120",
  );
});
```

- [ ] **Step 5.2: Run tests to verify pass**

Run: `cd frontend && npx vitest run src/portfolio/AddEditDrawer.test.tsx`
Expected: full suite PASS.

- [ ] **Step 5.3: Commit**

```bash
git add frontend/src/portfolio/AddEditDrawer.test.tsx
git commit -m "$(cat <<'EOF'
test(portfolio): cover stacked-apply and null-cost-basis edge cases

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Final verification

- [ ] **Step 6.1: Full frontend tests**

Run: `cd frontend && npx vitest run`
Expected: all PASS.

- [ ] **Step 6.2: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no output.

- [ ] **Step 6.3: Visual smoke (manual)**

Start the dev server (`cd frontend && npm run dev`), open the portfolio page, click an existing holding's edit button, and verify:
- "Adjust position" section appears above the Shares field.
- Buy/Sell toggle works; clicking either updates the active state.
- Entering qty + price shows the `-> N shares @ avg $X` preview.
- Apply writes computed values into the Shares and Cost Basis fields and clears the sub-form.
- Save persists the position (server round-trip; check the Holdings table reflects the new shares + cost).
- Add Position (create mode) does NOT show the Adjust section.

If any step fails, capture the failure and stop.

- [ ] **Step 6.4: (no commit — verification only)**

---

## Self-Review

- **Spec coverage:**
  - UX layout (Adjust section above raw fields, edit-mode only) — Task 2.
  - Action toggle (Buy/Sell) — Task 2.
  - Shares + Price inputs required for both — Task 2.
  - Apply math (Buy blend, null edges, Sell unchanged cost) — Task 1 (pure) + Tasks 3/4/5 (integration).
  - Validation (sell over-qty, null shares) — Task 4.
  - Live preview line — Task 2 (`adjust-preview` testid asserted by Task 4 error case; happy preview is observable but uncovered by test). Acceptable: the preview is a thin render of `computeBlend` already covered.
  - Stacked applies — Task 5.
  - Sub-form clears after Apply — Task 3.
  - Save flow unchanged — implicit (no edits to submit handler).

- **Placeholders:** none.

- **Type consistency:** `parseDecimal` returns `number | null`; `computeBlend` takes `currentShares: number | null`, `currentCostBasis: number | null`. `onApply` callback signature `(newShares: string, newCostBasis: string | null) => void` matches both sides.

- **Note on test verification timing:** Steps 3.2, 4.2, and 5.2 expect tests to PASS rather than FAIL because the implementation in Task 2 is comprehensive. Each subsequent task is locking behavior rather than driving new code. This is intentional and noted in the spec — the Adjust section is small enough that splitting "render scaffold" and "behavior" across tasks would be artificial.

Plan complete and saved to `docs/superpowers/plans/2026-05-11-edit-position-adjust-shares.md`.
