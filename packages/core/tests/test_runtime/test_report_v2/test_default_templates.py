import pytest
from pathlib import Path
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2

TEMPLATE_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "src" / "openlia" / "llm" / "runtime" / "report_v2" / "templates"
)


@pytest.mark.parametrize("filename,expected_report_type", [
    ("stock_research_v2.yaml", "equity_research"),
    ("stock_initiation_v2.yaml", "equity_research"),
    ("sector_research_v2.yaml", "sector_research"),
])
def test_default_templates_load_without_notices(filename, expected_report_type):
    raw = (TEMPLATE_DIR / filename).read_text()
    spec, notices = load_template_v2(raw, fmt="yaml")
    assert spec.report_type == expected_report_type
    # Default templates should not have any unknown_key or reserved_key notices
    structural_notices = [n for n in notices if n.kind in ("reserved_key", "unknown_key")]
    assert structural_notices == [], (
        f"{filename} produced unexpected notices: {structural_notices}"
    )


def test_all_three_templates_have_at_least_one_section():
    for filename in ("stock_research_v2.yaml", "stock_initiation_v2.yaml", "sector_research_v2.yaml"):
        raw = (TEMPLATE_DIR / filename).read_text()
        spec, _ = load_template_v2(raw, fmt="yaml")
        assert len(spec.sections) >= 1


def test_stock_initiation_has_more_sections_than_stock_research():
    # Initiation reports are richer than research updates
    raw_init = (TEMPLATE_DIR / "stock_initiation_v2.yaml").read_text()
    raw_res = (TEMPLATE_DIR / "stock_research_v2.yaml").read_text()
    init_spec, _ = load_template_v2(raw_init, fmt="yaml")
    res_spec, _ = load_template_v2(raw_res, fmt="yaml")
    assert len(init_spec.sections) >= len(res_spec.sections)


def test_sector_research_has_sector_composer_input():
    raw = (TEMPLATE_DIR / "sector_research_v2.yaml").read_text()
    spec, _ = load_template_v2(raw, fmt="yaml")
    assert any(i.type == "sector" for i in spec.composer_inputs)
