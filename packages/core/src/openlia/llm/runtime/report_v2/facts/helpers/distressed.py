"""Distressed-mode helpers (WS7)."""

from __future__ import annotations

from datetime import date, datetime


def _parse_year(value: date | datetime | str) -> int:
    if isinstance(value, (date, datetime)):
        return value.year
    s = str(value).strip()
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    raise ValueError(f"unparseable maturity date: {value!r}")


def debt_maturity_wall(debt_tranches: list[dict]) -> dict:
    """Aggregate principal due per future year.

    Each tranche: {amount: float, maturity_date: date|datetime|str, coupon: float}."""
    by_year: dict[int, float] = {}
    for t in debt_tranches:
        year = _parse_year(t["maturity_date"])
        by_year[year] = by_year.get(year, 0.0) + float(t["amount"])
    rows = [{"year": y, "principal_due": amt} for y, amt in sorted(by_year.items())]
    return {
        "by_year": by_year,
        "rows": rows,
        "total_principal": sum(by_year.values()),
    }


def recovery_waterfall(
    pre_petition_capital_structure: list[dict],
    plan_of_reorganization_recoveries: list[dict],
) -> dict:
    """Pre-petition claim → post-emergence recovery per class.

    `pre_petition_capital_structure`: each {class, claim_amount, seniority_rank}.
    `plan_of_reorganization_recoveries`: each {class, recovery_amount, form}."""
    recoveries_by_class: dict[str, dict] = {
        r["class"]: r for r in plan_of_reorganization_recoveries
    }
    rows: list[dict] = []
    total_claims = 0.0
    total_recovery = 0.0
    for tier in pre_petition_capital_structure:
        cls = tier["class"]
        claim = float(tier["claim_amount"])
        rec_row = recoveries_by_class.get(cls)
        recovery = float(rec_row["recovery_amount"]) if rec_row else 0.0
        form = rec_row.get("form") if rec_row else None
        pct = (recovery / claim) if claim > 0 else None
        rows.append(
            {
                "class": cls,
                "seniority_rank": tier.get("seniority_rank"),
                "claim_amount": claim,
                "recovery_amount": recovery,
                "recovery_pct": pct,
                "form": form,
            }
        )
        total_claims += claim
        total_recovery += recovery
    return {
        "rows": rows,
        "total_claims": total_claims,
        "total_recovery": total_recovery,
        "blended_recovery_pct": (total_recovery / total_claims) if total_claims > 0 else None,
    }
