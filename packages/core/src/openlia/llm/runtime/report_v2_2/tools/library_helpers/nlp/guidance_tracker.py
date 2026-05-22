"""guidance_tracker — management guidance vs actuals track record.

Registered name: "guidance_tracker"
Category: LLM_NLP

Tracks management guidance vs actual results over up to 8 quarters.
Per-quarter verdict: beat_modest | beat_large | within_range | miss.

Beat/miss logic (per design §7.6 + audit fix §9):
- beat_modest:   actual > guidance_high by <= 5%
- beat_large:    actual > guidance_high by > 5%
- within_range:  guidance_low <= actual <= guidance_high
- miss:          actual < guidance_low

Guidance accuracy heuristic (opinionated; see design §7.6):
- within_range = 1.0
- beat_modest  = 1.0
- beat_large   = 0.7  (chronic large beats = sandbagging heuristic)
- miss         = 0.0

Weights are user-overridable.

Per helpers-design §7.6 (label "guidance_tracker" per audit §9).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS: dict[str, float] = {
    "within_range": 1.0,
    "beat_modest": 1.0,
    "beat_large": 0.7,
    "miss": 0.0,
}


def _verdict(
    actual: float,
    guidance_low: float,
    guidance_high: float,
    beat_large_threshold: float = 0.05,
) -> str:
    """Classify a single guidance issuance vs actual.

    Args:
        actual: Actual reported value.
        guidance_low: Low end of guidance range.
        guidance_high: High end of guidance range.
        beat_large_threshold: Fractional excess above guidance_high for beat_large.

    Returns:
        One of: beat_modest, beat_large, within_range, miss.
    """
    if actual < guidance_low:
        return "miss"
    if guidance_low <= actual <= guidance_high:
        return "within_range"
    # actual > guidance_high
    excess_pct = (actual - guidance_high) / abs(guidance_high) if guidance_high != 0 else 0.0
    if excess_pct > beat_large_threshold:
        return "beat_large"
    return "beat_modest"


def execute(
    guidance_records: list[dict[str, Any]],
    beat_large_threshold: float = 0.05,
    accuracy_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build guidance-vs-actual track record.

    Args:
        guidance_records: List of dicts, each with keys:
            - guidance_quarter (str): period when guidance was issued (e.g. "Q4 FY24")
            - guidance_for_period (str): period the guidance covers (e.g. "Q1 FY25")
            - guidance_issued (dict): with keys revenue_low, revenue_high,
              and optionally eps_low, eps_high (all numeric)
            - actual_results (dict): with keys revenue and optionally eps (numeric)
        beat_large_threshold: Fractional excess above guidance_high to classify as
            beat_large (default 0.05 = 5%).
        accuracy_weights: Override weights for accuracy heuristic. Dict with keys
            within_range, beat_modest, beat_large, miss. Defaults per design §7.6.

    Returns:
        Dict with quarters_analyzed, guidance_track_record (per-quarter verdict),
        summary (beat_rate, miss_rate, within_range_rate, avg_revenue_surprise_pct,
        guidance_accuracy_heuristic, narrative).

    Raises:
        ValueError: If guidance_records is empty or a required key is missing.
    """
    if not guidance_records:
        raise ValueError("guidance_records must not be empty.")

    weights = {**_DEFAULT_WEIGHTS, **(accuracy_weights or {})}

    track_record: list[dict[str, Any]] = []

    for rec in guidance_records:
        for key in ("guidance_quarter", "guidance_for_period", "guidance_issued", "actual_results"):
            if key not in rec:
                raise ValueError(f"guidance_records entry missing required key: {key!r}")

        gi = rec["guidance_issued"]
        ar = rec["actual_results"]

        if "revenue_low" not in gi or "revenue_high" not in gi:
            raise ValueError("guidance_issued must have revenue_low and revenue_high keys.")
        if "revenue" not in ar:
            raise ValueError("actual_results must have a revenue key.")

        rev_verdict = _verdict(
            actual=float(ar["revenue"]),
            guidance_low=float(gi["revenue_low"]),
            guidance_high=float(gi["revenue_high"]),
            beat_large_threshold=beat_large_threshold,
        )

        entry: dict[str, Any] = {
            "guidance_quarter": rec["guidance_quarter"],
            "guidance_for_period": rec["guidance_for_period"],
            "guidance_issued": gi,
            "actual_results": ar,
            "verdict": rev_verdict,
        }

        # EPS verdict if available
        if "eps_low" in gi and "eps_high" in gi and "eps" in ar:
            eps_verdict = _verdict(
                actual=float(ar["eps"]),
                guidance_low=float(gi["eps_low"]),
                guidance_high=float(gi["eps_high"]),
                beat_large_threshold=beat_large_threshold,
            )
            entry["eps_verdict"] = eps_verdict

        track_record.append(entry)

    n = len(track_record)
    verdicts = [e["verdict"] for e in track_record]

    beat_count = sum(1 for v in verdicts if v in ("beat_modest", "beat_large"))
    miss_count = sum(1 for v in verdicts if v == "miss")
    within_count = sum(1 for v in verdicts if v == "within_range")

    beat_rate = round(beat_count / n, 4)
    miss_rate = round(miss_count / n, 4)
    within_rate = round(within_count / n, 4)

    # Average revenue surprise pct — only for beats and within-range
    surprises: list[float] = []
    for rec, _entry in zip(guidance_records, track_record, strict=True):
        gi = rec["guidance_issued"]
        ar = rec["actual_results"]
        midpoint = (float(gi["revenue_low"]) + float(gi["revenue_high"])) / 2.0
        if midpoint != 0:
            surprises.append((float(ar["revenue"]) - midpoint) / abs(midpoint))

    avg_surprise = round(sum(surprises) / len(surprises) * 100, 4) if surprises else 0.0

    # Guidance accuracy heuristic
    accuracy_score = round(sum(weights.get(v, 0.0) for v in verdicts) / n, 4)

    # Narrative
    beat_pct = round((beat_count + within_count) / n * 100)
    narrative = (
        f"Management delivered above or within guidance {beat_pct}% of the time "
        f"over {n} quarter{'s' if n != 1 else ''}. "
        f"Guidance accuracy heuristic: {accuracy_score:.2f} "
        f"(1.0 = always within range; chronic large beats discounted to 0.7 "
        f"per sandbagging heuristic)."
    )

    return {
        "quarters_analyzed": n,
        "guidance_track_record": track_record,
        "summary": {
            "beat_rate": beat_rate,
            "miss_rate": miss_rate,
            "within_range_rate": within_rate,
            "avg_revenue_surprise_pct": avg_surprise,
            "guidance_accuracy_heuristic": accuracy_score,
            "narrative": narrative,
        },
    }


from openlia.llm.runtime.report_v2_2 import (  # noqa: E402
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper  # noqa: E402

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="guidance_tracker",
        category=Category.LLM_NLP,
        one_liner=(
            "Management guidance vs actuals track record with beat/miss/within-range "
            "classification."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Build an 8-quarter guidance-vs-actual track record. Classifies each quarter "
            "as beat_modest, beat_large, within_range, or miss. Computes beat rate, "
            "miss rate, average revenue surprise, and a guidance accuracy heuristic "
            "(opinionated: chronic large beats scored lower as sandbagging signal)."
        ),
        when_to_use=[
            "Management credibility section of any earnings update or initiation.",
            "Feeding qualitative commentary alongside earnings_surprise_tracker.",
            "Cross-referencing with tone_shift_qoq to see if tone matches guidance accuracy.",
        ],
        when_not_to_use=[
            "When fewer than 2 guidance periods are available — insufficient for trend.",
            "When guidance ranges are not available — use earnings_surprise_tracker instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "guidance_records": HelperParam(
                type="list[dict]",
                required=True,
                description=(
                    "List of guidance issuance records. Each dict: "
                    "guidance_quarter, guidance_for_period, "
                    "guidance_issued (revenue_low, revenue_high, [eps_low, eps_high]), "
                    "actual_results (revenue, [eps])."
                ),
            ),
            "beat_large_threshold": HelperParam(
                type="float",
                required=False,
                default=0.05,
                description=(
                    "Fractional excess above guidance_high to classify as beat_large. "
                    "Default 0.05 (5%)."
                ),
            ),
            "accuracy_weights": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Override accuracy heuristic weights. Keys: within_range, beat_modest, "
                    "beat_large, miss. Default: {within_range:1.0, beat_modest:1.0, "
                    "beat_large:0.7, miss:0.0}."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="guidance_tracker_output",
                type="guidance_tracker_output",
                description=(
                    "quarters_analyzed, guidance_track_record (per-quarter with verdict), "
                    "summary (beat_rate, miss_rate, within_range_rate, "
                    "avg_revenue_surprise_pct, guidance_accuracy_heuristic, narrative)."
                ),
            ),
        ],
        produces_artifacts=["guidance_tracker_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.FACTUAL_INCONSISTENCY,
    ],
)

register_helper(_SCHEMA, execute)
