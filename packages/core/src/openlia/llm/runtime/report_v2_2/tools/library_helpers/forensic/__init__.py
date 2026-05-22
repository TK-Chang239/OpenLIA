"""Forensic and credit integrity helpers bundle (PR 2.6).

4 helpers:
  altman_z_variants        — Altman Z-score in 4 variants (Z, Z', Z", EM Z")
  dividend_safety_panel    — Dividend sustainability, payout ratios, stress test
  beneish_m_score          — Earnings manipulation M-score (Beneish 1999)
  statement_integrity_bundle — Composite integrity aggregator (18-list)

All self-register via register_helper() on import.
"""

from . import (  # noqa: F401
    altman_z_variants,
    beneish_m_score,
    dividend_safety_panel,
    statement_integrity_bundle,
)
