"""Extended (discoverable) tool registry for v3.

The v3 model always sees a small *core* tool set (data, valuation,
output, web_search). Everything else — the long tail of forensic
scores, sector KPI packs, statement-integrity panels, NLP extractors —
lives here in the *extended* tier. Extended tools are NOT placed in the
model's request up front. Instead the model calls ``find_tools`` (see
``find_tools.py``) to discover the ones a given subject needs; matched
tools are then injected into subsequent turns and become callable.

This keeps per-turn tool count small (high selection accuracy) and the
always-on token cost flat, while letting the catalog grow toward the
~120-helper design without inflating context. Adding a helper later is
a single registration here — no loop, prompt, or schema changes.

Each extended tool carries:

  - ``tool``     the underlying ``ResearchTool`` (dispatched exactly
                 like a core tool once activated; appends to the
                 citation ledger so its result is citable)
  - ``category`` one of ``CATEGORY_INDEX`` — the coarse grouping the
                 capability index advertises and ``find_tools`` filters on
  - ``summary``  a one-line blurb the discovery result shows the model

The three tools built here (``piotroski_f_score``, ``beneish_m_score``,
``roic_panel``) are real, deterministic implementations that exercise
the discovery loop end-to-end. They take numeric inputs directly (same
shape as the valuation tools) rather than fetching data, so they have
no transport dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
)
from ...report_v2_3.schemas import ComputedSource
from ..ledger import CitationLedger

# ---------------------------------------------------------------------------
# Capability index — the always-loaded Layer 1 map (category -> summary).
# The model reads this to know what CAN be summoned via find_tools without
# seeing every individual schema. Categories mirror the analytic concerns
# of the helper-stack design.
# ---------------------------------------------------------------------------

CATEGORY_INDEX: dict[str, str] = {
    "business_quality": (
        "Returns on capital and capital allocation: ROIC/ROCE/ROIIC, "
        "economic profit, shareholder yield, FCF conversion."
    ),
    "forensic_ratios": (
        "Quality/manipulation/bankruptcy scores: Piotroski F-score, "
        "Beneish M-score, Altman Z, cash conversion cycle."
    ),
    "statement_integrity": (
        "Statement-tie checks, one-time-item bridges, organic vs "
        "inorganic growth, constant-currency, common-size statements."
    ),
    "valuation_deliverables": (
        "Valuation visuals and solvers: reverse DCF, scenario weighting, "
        "football field, tornado, FY-to-FY waterfalls."
    ),
    "trend_earnings_quality": (
        "Trend regressions: margin trajectory, operating leverage, SBC "
        "intensity, share-count dilution."
    ),
    "risk_macro": (
        "Risk and macro context: drawdown panel, yield-curve shape, commodity exposure."
    ),
    "nlp_extraction": (
        "Filing/transcript extraction: MD&A, guidance tracking, risk factors, management tone."
    ),
    "sector_modules": ("Sector KPI packs: banks, REITs, insurance, energy/E&P, pharma rNPV."),
    "market_data_extras": (
        "Extended market data and stats: technicals, options chains, OLS/multi-factor regressions."
    ),
}


@dataclass(frozen=True, slots=True)
class ExtendedTool:
    """One discoverable tool plus its discovery metadata."""

    tool: ResearchTool
    category: str
    summary: str

    @property
    def name(self) -> str:
        return self.tool.descriptor.name


def match_extended_tools(
    registry: dict[str, ExtendedTool],
    *,
    query: str | None,
    category: str | None,
    limit: int = 8,
) -> tuple[list[ExtendedTool], int]:
    """Match extended tools by category and/or keyword.

    Returns ``(matched, total_matched)`` where ``matched`` is capped at
    ``limit`` and ``total_matched`` is the count before truncation (so
    the caller can tell the model to narrow its query).

    Matching:
      - ``category`` (if given) filters to that exact category.
      - ``query`` (if given) keyword-scores each candidate by how many
        query tokens appear in its name + summary + description; only
        positive-scoring tools survive, sorted by score desc then name.
      - With only a category, all tools in it are returned (name order).
    """
    candidates = list(registry.values())
    if category is not None:
        cat = category.strip().lower()
        candidates = [e for e in candidates if e.category == cat]

    scored: list[tuple[int, ExtendedTool]]
    if query and query.strip():
        tokens = [t for t in _tokenize(query) if t]
        scored = []
        for entry in candidates:
            haystack = _tokenize(
                f"{entry.name} {entry.summary} {entry.tool.descriptor.description}"
            )
            score = sum(1 for tok in tokens if tok in haystack)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1].name))
        ordered = [entry for _, entry in scored]
    else:
        ordered = sorted(candidates, key=lambda e: e.name)

    total = len(ordered)
    return ordered[:limit], total


def _tokenize(text: str) -> set[str]:
    """Lowercase alnum tokens. Splits on any non-alphanumeric char so
    'ev_ebitda' and 'roic-wacc' break into searchable parts."""
    out: list[str] = []
    current: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            current.append(ch)
        elif current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return set(out)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_extended_tools(*, ledger: CitationLedger) -> dict[str, ExtendedTool]:
    """Build the extended tool registry (name -> ExtendedTool).

    Seeded with three real forensic/quality helpers. Append new helpers
    here as they graduate — each is one entry and costs zero per-run
    context until the model discovers it.
    """
    entries = [
        ExtendedTool(
            tool=_make_computed_tool(
                ledger=ledger,
                name="piotroski_f_score",
                description=(
                    "Compute the 9-criterion Piotroski F-score (0-9) measuring "
                    "fundamental strength from profitability, leverage/liquidity, "
                    "and operating-efficiency signals. Pass current + prior-year "
                    "figures. Higher is stronger; 8-9 is high quality, 0-2 weak."
                ),
                parameters=_PIOTROSKI_PARAMETERS,
                runner=_run_piotroski,
            ),
            category="forensic_ratios",
            summary="9-point Piotroski fundamental-strength score.",
        ),
        ExtendedTool(
            tool=_make_computed_tool(
                ledger=ledger,
                name="beneish_m_score",
                description=(
                    "Compute the 8-variable Beneish M-score for earnings-"
                    "manipulation likelihood from the standard indices (DSRI, "
                    "GMI, AQI, SGI, DEPI, SGAI, TATA, LVGI). M > -1.78 flags an "
                    "elevated manipulation probability."
                ),
                parameters=_BENEISH_PARAMETERS,
                runner=_run_beneish,
            ),
            category="forensic_ratios",
            summary="8-input Beneish earnings-manipulation detector.",
        ),
        ExtendedTool(
            tool=_make_computed_tool(
                ledger=ledger,
                name="roic_panel",
                description=(
                    "Compute a return-on-invested-capital panel: ROIC, prior "
                    "ROIC, incremental ROIC (ROIIC), the ROIC-WACC spread, and "
                    "economic profit. Pass NOPAT + invested capital for current "
                    "and prior periods plus WACC."
                ),
                parameters=_ROIC_PARAMETERS,
                runner=_run_roic_panel,
            ),
            category="business_quality",
            summary="ROIC / ROIIC / economic-profit panel vs WACC.",
        ),
    ]
    return {e.name: e for e in entries}


def _make_computed_tool(
    *,
    ledger: CitationLedger,
    name: str,
    description: str,
    parameters: dict[str, Any],
    runner: Any,
) -> ResearchTool:
    """Wrap a pure-math runner as a ledger-aware ResearchTool.

    Mirrors the valuation-tool pattern: run the math, append one ledger
    entry with the input parameters as provenance, and hand the model a
    payload prefixed with the assigned source_id so it knows what to
    cite.
    """

    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            result = runner(args)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"{name} failed: {exc!s}") from exc

        provenance = ComputedSource(
            method=name,
            derived_from=sorted(args.keys()) or ["(no_inputs)"],
        )
        entry = ledger.append(
            tool_name=name,
            arguments=dict(args),
            result_summary=f"{name} computed",
            provenance=_provenance_to_dict(provenance),
        )
        return ToolResult(
            payload={"source_id": entry.source_id, "result": result},
            provenance=provenance,
            summary=f"{name} -> {entry.source_id}",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(name=name, description=description, parameters=parameters),
        execute=_execute,
    )


# ---------------------------------------------------------------------------
# Stub math — real implementations
# ---------------------------------------------------------------------------


def _run_piotroski(args: dict[str, Any]) -> dict[str, Any]:
    net_income = float(args["net_income"])
    operating_cash_flow = float(args["operating_cash_flow"])
    roa_current = float(args["roa_current"])
    roa_prior = float(args["roa_prior"])
    ltd_ratio_current = float(args["long_term_debt_ratio_current"])
    ltd_ratio_prior = float(args["long_term_debt_ratio_prior"])
    current_ratio_current = float(args["current_ratio_current"])
    current_ratio_prior = float(args["current_ratio_prior"])
    shares_current = float(args["shares_current"])
    shares_prior = float(args["shares_prior"])
    gross_margin_current = float(args["gross_margin_current"])
    gross_margin_prior = float(args["gross_margin_prior"])
    asset_turnover_current = float(args["asset_turnover_current"])
    asset_turnover_prior = float(args["asset_turnover_prior"])

    criteria: dict[str, bool] = {
        "positive_net_income": net_income > 0,
        "positive_operating_cash_flow": operating_cash_flow > 0,
        "rising_roa": roa_current > roa_prior,
        "cash_flow_exceeds_net_income": operating_cash_flow > net_income,
        "falling_leverage": ltd_ratio_current < ltd_ratio_prior,
        "rising_current_ratio": current_ratio_current > current_ratio_prior,
        "no_dilution": shares_current <= shares_prior,
        "rising_gross_margin": gross_margin_current > gross_margin_prior,
        "rising_asset_turnover": asset_turnover_current > asset_turnover_prior,
    }
    score = sum(1 for passed in criteria.values() if passed)
    return {
        "f_score": score,
        "max_score": 9,
        "criteria": criteria,
        "interpretation": _piotroski_band(score),
    }


def _piotroski_band(score: int) -> str:
    if score >= 8:
        return "high quality"
    if score >= 5:
        return "moderate"
    if score >= 3:
        return "weak"
    return "very weak"


def _run_beneish(args: dict[str, Any]) -> dict[str, Any]:
    dsri = float(args["dsri"])
    gmi = float(args["gmi"])
    aqi = float(args["aqi"])
    sgi = float(args["sgi"])
    depi = float(args["depi"])
    sgai = float(args["sgai"])
    tata = float(args["tata"])
    lvgi = float(args["lvgi"])

    m_score = (
        -4.84
        + 0.92 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )
    threshold = -1.78
    return {
        "m_score": m_score,
        "threshold": threshold,
        "likely_manipulator": m_score > threshold,
        "inputs": {
            "dsri": dsri,
            "gmi": gmi,
            "aqi": aqi,
            "sgi": sgi,
            "depi": depi,
            "sgai": sgai,
            "tata": tata,
            "lvgi": lvgi,
        },
    }


def _run_roic_panel(args: dict[str, Any]) -> dict[str, Any]:
    nopat = float(args["nopat"])
    invested_capital = float(args["invested_capital"])
    prior_nopat = float(args["prior_nopat"])
    prior_invested_capital = float(args["prior_invested_capital"])
    wacc = float(args["wacc"])

    if invested_capital == 0 or prior_invested_capital == 0:
        raise ToolExecutionError("invested_capital and prior_invested_capital must be non-zero.")

    roic = nopat / invested_capital
    prior_roic = prior_nopat / prior_invested_capital
    delta_ic = invested_capital - prior_invested_capital
    roiic = (nopat - prior_nopat) / delta_ic if delta_ic != 0 else None
    spread = roic - wacc
    economic_profit = spread * invested_capital
    return {
        "roic": roic,
        "prior_roic": prior_roic,
        "roiic": roiic,
        "roic_wacc_spread": spread,
        "economic_profit": economic_profit,
        "creates_value": spread > 0,
    }


# ---------------------------------------------------------------------------
# Parameter schemas
# ---------------------------------------------------------------------------

_PIOTROSKI_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "net_income": {"type": "number", "description": "Current-year net income."},
        "operating_cash_flow": {
            "type": "number",
            "description": "Current-year cash from operations.",
        },
        "roa_current": {"type": "number", "description": "Current-year return on assets."},
        "roa_prior": {"type": "number", "description": "Prior-year return on assets."},
        "long_term_debt_ratio_current": {
            "type": "number",
            "description": "Current LT debt / total assets.",
        },
        "long_term_debt_ratio_prior": {
            "type": "number",
            "description": "Prior LT debt / total assets.",
        },
        "current_ratio_current": {"type": "number"},
        "current_ratio_prior": {"type": "number"},
        "shares_current": {"type": "number", "description": "Current diluted share count."},
        "shares_prior": {"type": "number", "description": "Prior diluted share count."},
        "gross_margin_current": {"type": "number"},
        "gross_margin_prior": {"type": "number"},
        "asset_turnover_current": {"type": "number"},
        "asset_turnover_prior": {"type": "number"},
    },
    "required": [
        "net_income",
        "operating_cash_flow",
        "roa_current",
        "roa_prior",
        "long_term_debt_ratio_current",
        "long_term_debt_ratio_prior",
        "current_ratio_current",
        "current_ratio_prior",
        "shares_current",
        "shares_prior",
        "gross_margin_current",
        "gross_margin_prior",
        "asset_turnover_current",
        "asset_turnover_prior",
    ],
    "additionalProperties": False,
}

_BENEISH_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dsri": {"type": "number", "description": "Days Sales in Receivables Index."},
        "gmi": {"type": "number", "description": "Gross Margin Index."},
        "aqi": {"type": "number", "description": "Asset Quality Index."},
        "sgi": {"type": "number", "description": "Sales Growth Index."},
        "depi": {"type": "number", "description": "Depreciation Index."},
        "sgai": {"type": "number", "description": "SG&A Index."},
        "tata": {"type": "number", "description": "Total Accruals to Total Assets."},
        "lvgi": {"type": "number", "description": "Leverage Index."},
    },
    "required": ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "tata", "lvgi"],
    "additionalProperties": False,
}

_ROIC_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "nopat": {"type": "number", "description": "Current net operating profit after tax."},
        "invested_capital": {"type": "number", "description": "Current invested capital."},
        "prior_nopat": {"type": "number", "description": "Prior-period NOPAT."},
        "prior_invested_capital": {
            "type": "number",
            "description": "Prior-period invested capital.",
        },
        "wacc": {"type": "number", "description": "Weighted average cost of capital (e.g. 0.09)."},
    },
    "required": ["nopat", "invested_capital", "prior_nopat", "prior_invested_capital", "wacc"],
    "additionalProperties": False,
}


def _provenance_to_dict(provenance: Any) -> dict[str, Any]:
    if hasattr(provenance, "model_dump"):
        try:
            return provenance.model_dump(mode="json")
        except Exception:
            pass
    return {"raw": str(provenance)}


__all__ = [
    "CATEGORY_INDEX",
    "ExtendedTool",
    "build_extended_tools",
    "match_extended_tools",
]
