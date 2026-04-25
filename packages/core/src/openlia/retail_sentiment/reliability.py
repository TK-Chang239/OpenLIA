"""Cross-source reliability weights for the Retail Sentiment metric engine.

Source reliability tiers (per spec §"Cross-Source Reliability"):
  financial_provider: 0.40 (highest tier — Finnhub / FMP / EODHD)
  social_media:       0.35 (mid-tier — Reddit / Twitter / StockTwits)
  cross_platform:     0.25 (lowest tier — aggregated/unsourced posts)

`_normalize_weights` re-bases any positive weight dict to sum to 1.0,
returning the defaults when the input is empty / all-zero / negative.
`weight_for_source` returns the per-source weight or 0.0 for an unknown
source, with the optional `default` escape hatch.
"""

from __future__ import annotations

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "financial_provider": 0.40,
    "social_media": 0.35,
    "cross_platform": 0.25,
}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, v) for v in weights.values())
    if total <= 0:
        return dict(DEFAULT_SOURCE_WEIGHTS)
    return {k: max(0.0, v) / total for k, v in weights.items()}


def weight_for_source(
    source: str,
    *,
    weights: dict[str, float] | None = None,
    default: float = 0.0,
) -> float:
    """Return the normalized weight for `source` from `weights` (defaults
    to `DEFAULT_SOURCE_WEIGHTS`). Returns `default` for an unknown source."""
    table = _normalize_weights(weights or DEFAULT_SOURCE_WEIGHTS)
    return table.get(source, default)
