---
name: rnpv_pipeline
category: sector_pharma
version: 1.0.0
produces_artifacts:
  - rnpv_pipeline_output
consumes_artifacts: []
---

# rnpv_pipeline — Pharma/Biotech Pipeline rNPV Engine

## Purpose

Compute risk-adjusted net present value (rNPV) of a pharmaceutical or biotech pipeline,
asset by asset.  Each clinical-stage asset is discounted by its probability of success (PoS),
a revenue ramp from launch to peak sales, generic erosion after patent expiry, and outgoing
royalty obligations.  The helper aggregates per-asset rNPVs to a total pipeline value and
flags value concentration and binary event risk.

This helper is mandatory for any pharma or biotech company where pipeline assets represent
more than 25% of estimated total enterprise value.

## When to use

- Initiating coverage on any pharma or biotech with meaningful clinical-stage pipeline.
- Post-trial readout update — re-enter the updated PoS for the relevant asset and rerun.
- Sector report benchmarking pipeline value across companies in the same therapeutic area.
- Single-asset biotech where the rNPV is essentially the entire equity value.

## When NOT to use

- **Royalty-pharma companies** (e.g., Royalty Pharma / RPRX): these hold royalty streams
  on already-approved drugs, not development-stage assets.  Use a stream-DCF instead.
  Refuse with: "royalty-pharma — use stream_dcf."
- **Pure commercial pharma** with no pipeline (only marketed drugs): use `dcf_engine` on
  the revenue/margin trajectory.  rNPV is not the right lens when development optionality
  is not material.
- **Medical devices**: the rNPV framework applies in principle, but PoS norms from pharma
  clinical attrition studies (Citeline) do not transfer to 510(k) or PMA pathways, which
  have fundamentally different regulatory risk profiles.

---

## Decision #5 — Why PoS is user-supplied

Execution-strategy decision #5 locks that no PoS lookup table ships in-repo.  The primary
industry source — Citeline (formerly Informa) stage-by-stage probability-of-success tables
from annual Pipeline and Intelligence reports — requires a commercial subscription.  Shipping
the data in-repo would create a license violation.

**What this means for callers:**  Every pipeline asset dict must include a `pos` field.
If `pos` is missing, the helper raises a `ValueError` with a message pointing to this decision
and recommending Citeline 2024 or a comparable source.

The module exposes `DEFAULT_POS_TABLE: dict[str, float] = {}` at module level so test code
can patch it without a runtime dependency.

### Phase-specific PoS norms (published industry reference — not shipped)

The following ranges are well-documented in the academic and industry literature and may be
used to calibrate user-supplied PoS values.  They are provided here as calibration guidance,
not as a lookup table the helper uses.

| Phase | Approximate PoS (all indications, small molecule) | Source |
|---|---|---|
| Preclinical | ~6-9% | DiMasi et al. (2016); Citeline 2023/2024 |
| Phase 1 | ~10-14% | DiMasi et al. (2016); Citeline 2024 |
| Phase 2 | ~22-31% | DiMasi et al. (2016); Citeline 2024 |
| Phase 3 | ~55-58% | DiMasi et al. (2016); Citeline 2024 |
| Filed (NDA/BLA) | ~85% | Citeline 2024; FDA approval rate data |
| Approved | 100% | N/A |

**Important modality adjustments** — small-molecule averages do not apply uniformly:

- **Oncology (all modalities)**: historically lower PoS than non-oncology by 5-15 percentage
  points at Phase 2; higher Phase 3 PoS for targeted therapies with companion diagnostics.
- **Cell / gene therapy**: Phase 1-2 PoS materially lower (high manufacturing and delivery risk);
  Phase 3 PoS can be higher when prior Phase 2 was single-arm vs substantial unmet need.
- **ADCs (antibody-drug conjugates)**: Phase 2 PoS closer to mAb rates than small molecule.
- **Rare disease / orphan**: Phase 2-3 PoS modestly higher due to smaller trial sizes,
  accelerated designation, and unmet-need premiums.

**Primary sources:**
- DiMasi, J.A., Grabowski, H.G., Hansen, R.W. (2016). "Innovation in the pharmaceutical
  industry: New estimates of R&D costs." *Journal of Health Economics*, 47, 20-33.
- Citeline (Informa) Annual Pipeline Analytics reports (2023, 2024).  Commercial subscription.
- Wong, C.H., Siah, K.W., Lo, A.W. (2019). "Estimation of clinical trial success rates and
  related parameters." *Biostatistics*, 20(2), 273-286.

---

## Decision #16 — royalty_stack_analyzer is internal

The royalty stack analyzer is an internal computation module of `rnpv_pipeline`, not a
standalone helper.  It computes the present value of royalty obligations owed to upstream
licensors (royalties-out) and reports this as `royalty_burden` in the per-asset output.

**Why internal, not standalone:**  The royalty stack is structurally dependent on the
per-asset revenue projection built inside `rnpv_pipeline`.  Extracting it as a separate
helper would require duplicating the revenue ramp and LOE decay logic or passing a full
revenue schedule as input — adding coordination overhead with no standalone use case.

**What it does:**  For each asset, it takes the gross revenue stream (pre-royalty), applies
the `royalty_rate` fraction year by year, and discounts the royalty payments back to the
present at the same `discount_rate` used for the asset rNPV.  The result is reported as
`royalty_burden` in each asset's output dict — the dollar PV of what is owed to licensors
over the life of that asset.

**Note:** Royalties are already netted from the revenue stream before computing NOPAT and
the risked NPV.  The `royalty_burden` field is a separate disclosure showing what was netted,
not a further deduction.

---

## Patent cliff modeling

**Mechanism:** After `patent_expiry`, the revenue stream applies a generic erosion curve:

| Year post-LOE | Fraction of pre-LOE peak revenue |
|---|---|
| Year of LOE (year 0) | 100% (last protected year) |
| Year +1 | 35% |
| Year +2 | 20% |
| Year +3 | 15% |
| Year +4+ | 10% |

The 80% loss in year +1 reflects small-molecule generic entry, where generics typically
capture 70-90% market share within 12-18 months.  This is calibrated to US market dynamics.

**Biologic / biosimilar erosion is slower:**  For biologic assets, the spec-default 35%
retention in year +1 should be set higher (60-70%) via the `ramp_curve`/custom assumptions.
The current implementation does not have a separate biosimilar decay curve — callers should
document any manual adjustment.  This is a known simplification.

**`patent_cliff_impact` field:**  Reported as (actual PV with LOE) minus (hypothetical PV
with no LOE decay).  The result is negative — it represents value destroyed by patent expiry.
Useful for narrating how much of a drug's theoretical value is stripped away by competition.

---

## Revenue ramp profiles

| Ramp | Profile | Suitable for |
|---|---|---|
| `standard` | 10%, 40%, 80%, 100% (year 1-4+) | Most oral small molecules, standard launch |
| `fast` | 65%, 100% (year 1-2+) | Biologics with orphan or urgent need, limited competition |
| `slow` | 5%, 15%, 35%, 65%, 90%, 100% (year 1-6+) | Competitive market, broad indication requiring guideline uptake |

---

## Common pitfalls

### 1. Ignoring development costs

The `peak_sales_estimate` and `pos` inputs capture value; this helper does not subtract
remaining R&D spend from rNPV.  If remaining development cost is material (typical for
Phase 1-2 assets), subtract the PV of future R&D from the rNPV externally and document it.
Failing to account for development costs overstates pipeline value, sometimes dramatically
for early-stage assets.

### 2. Overestimating peak sales

Peak sales estimates for Phase 2 assets are often based on total addressable market (TAM)
assumptions that assume best-in-class profile, full penetration, and no competitive entry.
Applying competitive and share discounts (50-70% of TAM for drugs entering a competitive
class) is standard institutional practice.  The helper does not enforce this — the analyst
must supply a disciplined `peak_sales_estimate`.

### 3. Ignoring competition at launch

This model is a single-asset DCF, not a competitive dynamics model.  If a drug enters a
market with 3-4 competitors already present, the effective peak-sales timeline and peak
level should reflect share constraints, not just the drug's clinical profile.

### 4. Using wrong discount rate

Development-stage single-asset biotechs: 11-14% is conventional (high binary risk).
Diversified pharma with large marketed portfolio: 8-10% is conventional (lower portfolio
risk).  Using an 8% discount rate for a Phase 1 single-asset biotech will substantially
overstate rNPV.

### 5. Not updating PoS after data events

Phase transitions should trigger a PoS step-up.  A Phase 2 asset advancing to Phase 3
jumps from ~25% to ~55% PoS, roughly doubling rNPV before any peak-sales revision.
Update the `pos` field promptly after public trial outcomes.

### 6. Treating negative rNPV as worthless

A negative rNPV on a Phase 1 or Phase 2 asset is informative, not a reason to assign zero
value.  It means the current-stage PoS does not justify the remaining R&D spend at the
current discount rate.  The asset still has option value — if Phase 3 PoS is 55%, the
rNPV will turn positive on advancement.  The narrative should explain this explicitly.

---

## Narrative discipline

- **Never say "Phase 2 readout will be a catalyst"** without also saying what the PoS is
  and what value change a success vs failure implies.  Binary events deserve quantified outcomes.
- **Binary risk language:** when top-1 asset share > 50%, the narrative must explicitly say
  so and quantify the downside (remove that asset's rNPV from total).
- **Single-asset biotech:** when there is only one asset, or one asset > 80% of rNPV,
  state plainly: "This is a binary outcome — the entire equity value hinges on [drug] [trial] readout."
- **Phase 3 updates:** the approved/filed PoS is ~85-100%, so these are near-commercial
  assets.  Narrative should bridge rNPV to per-share value and compare to current market price.
