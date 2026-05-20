"""SBC dilution bridge helper (WS7)."""

from __future__ import annotations


def sbc_dilution_bridge(
    beginning_shares: float,
    sbc_issuances: float,
    buybacks_in_shares: float,
    ending_shares: float,
    revenue_ttm: float,
    fcf_ttm: float,
) -> dict:
    """Reconcile share count change and report SBC as % of revenue and FCF.

    `sbc_issuances` and `buybacks_in_shares` are in *share* units; the
    reconciliation_gap surfaces other movements (options exercise, secondaries)."""
    computed_ending = beginning_shares + sbc_issuances - buybacks_in_shares
    gap = ending_shares - computed_ending
    sbc_pct_revenue = (sbc_issuances / revenue_ttm) if revenue_ttm != 0 else None
    sbc_pct_fcf = (sbc_issuances / fcf_ttm) if fcf_ttm != 0 else None
    return {
        "beginning_shares": beginning_shares,
        "sbc_issuances": sbc_issuances,
        "buybacks_in_shares": buybacks_in_shares,
        "ending_shares": ending_shares,
        "computed_ending": computed_ending,
        "reconciliation_gap": gap,
        "net_dilution_pct": ((ending_shares - beginning_shares) / beginning_shares)
        if beginning_shares != 0
        else None,
        "sbc_pct_revenue": sbc_pct_revenue,
        "sbc_pct_fcf": sbc_pct_fcf,
    }
