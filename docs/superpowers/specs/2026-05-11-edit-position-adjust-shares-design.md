# Edit Position — Adjust Shares (Buy/Sell) — Design

Date: 2026-05-11
Branch: `feat/portfolio-live-data`
Touchpoint: `frontend/src/portfolio/AddEditDrawer.tsx`

## Goal

Let users adjust an existing portfolio position by recording a Buy or Sell
transaction inside the **Edit Position** side drawer, instead of overwriting
the `Shares` and `Cost Basis` text fields by hand.

The current drawer only exposes raw fields, which gives no help with
cost-basis blending and is error-prone when the user actually means
"I bought 10 more at $145".

## Non-goals

- No backend changes. Backend already accepts `shares` + `cost_basis` via
  `HoldingPatch`; this feature only changes how those two values are computed
  inside the form before submit.
- No trade-lot / transaction history table. The price entered on Sell is
  captured in the sub-form state but discarded on Save. The design preserves
  forward compatibility with a future lot model, but does not build it.
- No realized-P/L tracking on Sell.
- No changes to the Add Position (create-mode) experience.

## UX

The drawer keeps its current shape. In **edit mode only**, a new
`AdjustPositionSection` is inserted above the raw `Shares` and `Cost Basis`
inputs.

```
+--- Edit Position --------------------------------------+
| Ticker: AAPL (disabled)                                |
|                                                        |
| --- Adjust position --------------------------------   |
| [ Buy ][ Sell ]                                        |
| Shares: [____]   Price per share: [____]   [Apply]     |
| -> 110 shares @ avg $130.41                            |
| (inline error here, if any)                            |
| ----------------------------------------------------   |
|                                                        |
| Shares *      [ 100 ]                                  |
| Cost Basis    [ 128.40 ]                               |
| Currency      [ USD ]                                  |
| Group         [ ... ]                                  |
| Notes         [ ... ]                                  |
|                                                        |
|                              [Cancel] [Save]           |
+--------------------------------------------------------+
```

The raw `Shares` and `Cost Basis` fields remain editable. Apply writes
computed values into them; Save submits the patch via the existing flow.

## Behavior

### Action toggle

Segmented control `[ Buy ] [ Sell ]`, default Buy. Toggling does not clear
qty/price inputs.

### Inputs

- **Shares (qty)** — text input, positive decimal, required.
- **Price per share** — text input, positive decimal, required for both
  Buy and Sell.

Empty either field → Apply disabled.

### Apply math

Let `S0 = current shares` (parsed from raw `form.shares`, `null` if empty),
`C0 = current cost basis` (parsed from raw `form.cost_basis`, `null` if
empty), `q = qty`, `p = price`.

**Buy:**
- `S1 = (S0 ?? 0) + q`
- If `S0` is `null`/`0` or `C0` is `null`: `C1 = p`
- Else: `C1 = ((S0 * C0) + (q * p)) / S1`

**Sell:**
- `S1 = S0 - q`
- `C1 = C0` (unchanged, even if null)
- Price `p` is captured in form state but not used in math.

### Apply validation

Errors render inline inside `AdjustPositionSection` and do **not** block the
outer Save button (the raw fields are still editable as an escape hatch).

| Condition                          | Error                                          |
|------------------------------------|------------------------------------------------|
| `q` does not parse / <= 0          | "Enter a positive share count."                |
| `p` does not parse / <= 0          | "Enter a positive price."                      |
| Sell and `S0` is null              | "Set current shares first."                    |
| Sell and `q > S0`                  | "Cannot sell more than current shares (S0)."   |

### After Apply succeeds

1. Update parent form: `setForm({ ...form, shares: String(S1), cost_basis: String(C1) })`.
2. Clear sub-form: `qty = ""`, `price = ""`, `error = null`.
3. Leave action toggle as-is.

The user can stack multiple applies before clicking Save — each Apply reads
the latest raw values from `form` and recomputes against them.

### Live preview

While both `qty` and `price` are non-empty and parse, show a single line
under the inputs:

`-> 110 shares @ avg $130.41`

If the preview would error (e.g. Sell qty > S0), show the error message
in the preview slot instead. The preview is the same string the user will
see written into the raw fields after Apply.

### Save flow

Unchanged. The drawer's existing `submit` handler reads `form.shares` and
`form.cost_basis` and calls `updateHolding(initial.id, patch)`.

## Component shape

```
function AdjustPositionSection({
  currentShares: Decimal | null,
  currentCostBasis: Decimal | null,
  onApply: (newShares: string, newCostBasis: string) => void,
}): JSX.Element
```

Lives inside `AddEditDrawer.tsx` as a private component. Local state:
`action`, `qty`, `price`. No effects, no async.

Decimal math runs on strings parsed to `Number` and formatted back with a
fixed precision (4 decimal places, trailing zeros trimmed) before being
written into `form.shares` / `form.cost_basis`. This matches how the raw
fields are already serialized over the wire as strings.

## Data flow

```
AdjustPositionSection (local state: action, qty, price)
   |
   | onApply(newShares, newCostBasis)
   v
AddEditDrawer (form state)
   |
   | submit -> updateHolding(id, { shares, cost_basis, currency, notes, groups })
   v
Backend (existing HoldingPatch flow)
```

## Tests

Extend `frontend/src/portfolio/AddEditDrawer.test.tsx`:

1. Section is rendered when `mode === "edit"`.
2. Section is **not** rendered when `mode === "create"`.
3. Buy: 100 sh @ $128 + buy 10 @ $145 → shares = 110, cost basis = `(100*128 + 10*145) / 110 = 129.5454...`, written into raw fields with normalized precision.
4. Buy with null current cost basis: cost basis becomes the buy price.
5. Buy with null current shares: shares = qty, cost basis = price.
6. Sell: 100 sh @ $128 - sell 25 @ $135 → shares = 75, cost basis = 128 (unchanged).
7. Sell when qty > current shares → inline error, raw fields unchanged.
8. Sell when current shares is null → inline error, raw fields unchanged.
9. Apply clears qty and price inputs but leaves action toggle.
10. Two sequential applies stack: buy 10 @ 145, then buy 5 @ 150, then save submits the once-blended-then-re-blended values.

## Edge cases

- **Negative-zero results:** prevent by clamping `S1 = max(S1, 0)`. With the
  Sell-over validation in place, this is defensive.
- **Decimal precision drift:** format to at most 4 decimal places before
  writing back. The backend already accepts arbitrary `Decimal`-as-string
  inputs.
- **User edits raw `Shares` after Apply:** next Apply reads the new raw
  value, recomputes against it. This is intentional.
- **User changes Currency mid-edit:** out of scope — currency does not
  participate in the blend math.

## Implementation order

1. Add `AdjustPositionSection` component inside `AddEditDrawer.tsx`.
2. Wire it into the edit-mode render path with an `onApply` that updates `form`.
3. Add the math helpers (`computeBlend`, `formatDecimal`) as local pure
   functions in the same file.
4. Add validation + inline error rendering.
5. Add live preview line.
6. Extend `AddEditDrawer.test.tsx` with the 10 cases above.
7. Run `npx tsc --noEmit` and the frontend test suite.
