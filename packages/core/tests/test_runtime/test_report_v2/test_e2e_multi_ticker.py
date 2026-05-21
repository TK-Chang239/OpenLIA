"""V3: Multi-ticker smoke against an AI-infra basket.

Marked ``@pytest.mark.slow`` and ``@pytest.mark.requires_llm`` per the plan
(docs/superpowers/plans/2026-05-21-equity-research-v2.2.md, Task V3). This test
exercises the full v2.2 pipeline against a real LLM tier. It is NOT run by
default — invoke explicitly when API keys are configured::

    OPENLIA_LLM_PROVIDER=anthropic \\
      ANTHROPIC_API_KEY=... \\
      uv run pytest packages/core/tests/test_runtime/test_report_v2/test_e2e_multi_ticker.py \\
        -v -m "slow"

Assertions per the plan:
- Every report HTML parses and has the three required sections (Sources, Run
  Summary, Verification History).
- No tickers produce FAILED Run Summaries on baseline outcomes.
- At least 80% of optional artifacts succeed across the basket.

Record results manually in a one-pager at
``docs/superpowers/specs/2026-05-XX-v2.2-validation-results.md`` (date filled at
validation time).
"""

from __future__ import annotations

import os

import pytest

# Curated AI-infrastructure basket. Mirrors the 14-ticker basket validated for
# v2 in observation 8534 (Equity Research v2 spec, 2026-05-20).
AI_INFRA_TICKERS = [
    "NVDA",
    "AMD",
    "AVGO",
    "MRVL",
    "TSM",
    "ASML",
    "AMAT",
    "LRCX",
    "KLAC",
    "ARM",
    "SMCI",
    "DELL",
    "ANET",
    "VRT",
]


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("OPENLIA_E2E_MULTI_TICKER"),
    reason=(
        "Multi-ticker E2E requires real LLM access. Set "
        "OPENLIA_E2E_MULTI_TICKER=1 and configure LLM provider env vars "
        "(ANTHROPIC_API_KEY, OPENAI_API_KEY) to run."
    ),
)
def test_v2_2_pipeline_runs_against_ai_infra_basket() -> None:
    """Run the v2.2 pipeline against each ticker in the basket.

    This is a placeholder implementation that documents the contract and
    skips by default. To activate, set OPENLIA_E2E_MULTI_TICKER=1 in the
    environment and fill in the orchestration below.

    Plan steps to fill in when activating:
      1. For each ticker: build composer_inputs, load stock_research_v2.yaml,
         run the full Clarifier -> ... -> assembler chain through a real LLM
         provider.
      2. Assert the resulting HTML contains <section id="sources">,
         <section id="run_summary">, <section id="verification_history">.
      3. Parse repo_item.run_summary; count FAILED outcomes (must be 0).
      4. Track optional-artifact success rate across all tickers; assert >= 0.80.
    """
    pytest.skip(
        "Multi-ticker E2E test is a placeholder. Wire to the real pipeline "
        "orchestration when activating; see docstring for the contract."
    )
