from openlia.llm.runtime.report_eu.default_template import build_default_template


def test_default_template_has_eight_sections():
    spec = build_default_template()
    ids = [s.id for s in spec.sections]
    assert ids == [
        "quick_take",
        "market_reaction",
        "key_financials",
        "operational_highlights",
        "forward_guidance",
        "earnings_call",
        "risk_assessment",
        "thesis_check",
    ]
    assert spec.template_id == "eu_default"
    assert spec.ticker_anchored is True
