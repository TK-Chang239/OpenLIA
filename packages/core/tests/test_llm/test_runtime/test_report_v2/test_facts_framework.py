from __future__ import annotations

import json
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.registry import default_registry

FACTS_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "src"
    / "openlia"
    / "llm"
    / "runtime"
    / "report_v2"
    / "frameworks"
    / "stock_initiation.facts.json"
)


def test_facts_file_exists_and_is_valid_json() -> None:
    data = json.loads(FACTS_PATH.read_text())
    assert "sections" in data
    assert isinstance(data["sections"], dict)


# Facts injected by the runner post-W3 rather than registered in the
# FactRegistry. `catalysts_recent` is packed by the WS3-A catalyst scanner
# (runner step) after `compile_pack` runs — it is intentionally absent from
# the registry.
RUNNER_INJECTED_FACTS: set[str] = {"catalysts_recent"}


def test_every_referenced_fact_is_registered() -> None:
    data = json.loads(FACTS_PATH.read_text())
    registered = set(default_registry.names()) | RUNNER_INJECTED_FACTS
    referenced: set[str] = set()
    for _section_id, fact_names in data["sections"].items():
        referenced.update(fact_names)
    unknown = referenced - registered
    assert not unknown, f"facts referenced but not registered: {sorted(unknown)}"


def test_cover_section_includes_key_metrics_facts() -> None:
    data = json.loads(FACTS_PATH.read_text())
    cover = set(data["sections"]["cover"])
    assert {"market_cap", "pe_ratio_ttm", "company_name"}.issubset(cover)


@pytest.mark.parametrize(
    "section_id",
    [
        "company_overview",
        "industry_overview",
        "products_and_services",
        "business_model",
        "management_team",
        "historical_financials",
        "financial_analysis",
        "financial_projections",
        "valuation_analysis",
        "competitive_analysis",
        "recent_developments",
        "competitive_advantages_and_weaknesses",
        "risk_analysis",
        "investment_recommendation",
        "cover",
    ],
)
def test_every_framework_section_declares_facts(section_id: str) -> None:
    data = json.loads(FACTS_PATH.read_text())
    assert section_id in data["sections"], f"missing facts list for {section_id}"
