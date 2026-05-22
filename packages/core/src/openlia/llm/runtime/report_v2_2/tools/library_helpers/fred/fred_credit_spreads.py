"""fred_credit_spreads — ICE BofA HY OAS, IG OAS, and 10Y Treasury from FRED public CSVs."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import requests

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# FRED public CSV download endpoint (no auth required)
_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Series IDs
_HY_OAS_SERIES = "BAMLH0A0HYM2"  # ICE BofA US High Yield OAS (%)
_IG_OAS_SERIES = "BAMLC0A0CM"  # ICE BofA US Corporate Master OAS (%)
_TSY_10Y_SERIES = "DGS10"  # 10-Year Treasury Constant Maturity Rate (%)

_TIMEOUT = 15  # seconds


def _fetch_latest(series_id: str) -> tuple[float, str]:
    """Fetch a FRED public CSV and return the most recent (value, date) pair.

    Raises RuntimeError on HTTP failure or if no data is available.
    """
    url = f"{_FRED_BASE}?id={series_id}"
    resp = requests.get(url, timeout=_TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"FRED HTTP {resp.status_code} for series {series_id!r}")

    df = pd.read_csv(io.StringIO(resp.text), parse_dates=["DATE"])
    df = df.rename(columns={series_id: "value"})
    df = df.dropna(subset=["value"])
    df = df[df["value"].astype(str) != "."]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])

    if df.empty:
        raise RuntimeError(f"No valid data returned from FRED for series {series_id!r}")

    latest = df.sort_values("DATE").iloc[-1]
    return float(latest["value"]), str(latest["DATE"].date())


def execute(series_override: dict[str, str] | None = None) -> dict[str, Any]:
    """Fetch latest ICE BofA HY OAS, IG OAS, and 10Y Treasury from FRED.

    Args:
        series_override: Optional dict to override series IDs, e.g.
            {"hy": "BAMLH0A0HYM2", "ig": "BAMLC0A0CM", "tsy": "DGS10"}.
            Only used for testing with mock series IDs.

    Returns:
        Dict with hy_oas (%), ig_oas (%), treasury_10y (%), as_of (ISO date),
        spread_differential (HY - IG), and source string.
    """
    ids = {
        "hy": _HY_OAS_SERIES,
        "ig": _IG_OAS_SERIES,
        "tsy": _TSY_10Y_SERIES,
    }
    if series_override:
        ids.update(series_override)

    hy_oas, hy_date = _fetch_latest(ids["hy"])
    ig_oas, ig_date = _fetch_latest(ids["ig"])
    tsy, tsy_date = _fetch_latest(ids["tsy"])

    # Use the latest available date across all three series
    as_of = max(hy_date, ig_date, tsy_date)

    return {
        "hy_oas": hy_oas,
        "ig_oas": ig_oas,
        "treasury_10y": tsy,
        "spread_differential": round(hy_oas - ig_oas, 4),
        "as_of": as_of,
        "source": "FRED via ICE BofA",
        "series_ids": {
            "hy_oas": ids["hy"],
            "ig_oas": ids["ig"],
            "treasury_10y": ids["tsy"],
        },
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="fred_credit_spreads",
        category=Category.ADAPTER,
        one_liner="ICE BofA HY OAS, IG OAS, and 10Y Treasury from FRED public CSVs.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the latest ICE BofA US High Yield and Investment Grade OAS spreads "
            "plus the 10Y Treasury rate from FRED public CSV endpoints. No API key required."
        ),
        when_to_use=[
            "Adding a credit market context section to an equity or macro research report.",
            "Checking whether current credit spreads signal risk-on or risk-off conditions.",
        ],
        when_not_to_use=[
            "Historical spread time series — this helper returns only the latest data point.",
            "Corporate bond yield calculations — OAS is spread only, not full yield.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "series_override": HelperParam(
                type="dict",
                required=False,
                default=None,
                description=(
                    "Optional dict overriding FRED series IDs. Keys: 'hy', 'ig', 'tsy'. "
                    "Leave None to use the standard ICE BofA / DGS10 series."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="credit_spreads",
                type="dict",
                description=(
                    "Dict with hy_oas (float, %), ig_oas (float, %), "
                    "treasury_10y (float, %), spread_differential (HY - IG), "
                    "as_of (ISO date string), source (str), series_ids (dict)."
                ),
            ),
        ],
        produces_artifacts=["fred_credit_spreads_output"],
        consumes_artifacts=[],
        data_dependencies=["fred.public_csv"],
    ),
)

register_helper(_SCHEMA, execute)
