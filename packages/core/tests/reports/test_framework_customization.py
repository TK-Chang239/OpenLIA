import pytest
from openlia.reports.frameworks.loader import (
    CustomSection,
    load_framework,
    load_framework_customized,
)


def test_customized_preserves_original_order():
    framework = load_framework("stock_update")
    original_ids = [s["id"] for s in framework["sections"]]
    enabled = {original_ids[2], original_ids[0]}  # out-of-order input
    result = load_framework_customized(
        "stock_update", enabled_section_ids=enabled, custom_sections=()
    )
    result_ids = [s["id"] for s in result["sections"]]
    assert result_ids == [original_ids[0], original_ids[2]]


def test_customized_appends_custom_sections_last():
    framework = load_framework("stock_update")
    first_id = framework["sections"][0]["id"]
    custom = (CustomSection(id="custom_esg_x1", title="ESG Footnote", description="Short note."),)
    result = load_framework_customized(
        "stock_update",
        enabled_section_ids={first_id},
        custom_sections=custom,
    )
    ids = [s["id"] for s in result["sections"]]
    assert ids[-1] == "custom_esg_x1"
    assert result["sections"][-1]["title"] == "ESG Footnote"
    assert "Short note." in result["sections"][-1]["instructions"]


def test_customized_rejects_unknown_section_id():
    with pytest.raises(ValueError, match="unknown section"):
        load_framework_customized(
            "stock_update",
            enabled_section_ids={"does_not_exist"},
            custom_sections=(),
        )


def test_customized_empty_enabled_keeps_only_customs():
    custom = (CustomSection(id="custom_only_x1", title="Only Custom", description=None),)
    result = load_framework_customized(
        "stock_update",
        enabled_section_ids=set(),
        custom_sections=custom,
    )
    assert [s["id"] for s in result["sections"]] == ["custom_only_x1"]


def test_customized_does_not_mutate_cached_framework():
    before = load_framework("stock_update")
    before_count = len(before["sections"])
    load_framework_customized(
        "stock_update",
        enabled_section_ids=set(),
        custom_sections=(CustomSection(id="custom_q_x1", title="Q", description="r"),),
    )
    after = load_framework("stock_update")
    assert len(after["sections"]) == before_count


def test_customized_preserves_cover_and_top_level_keys():
    framework = load_framework("stock_initiation")
    first_id = framework["sections"][0]["id"]
    result = load_framework_customized(
        "stock_initiation",
        enabled_section_ids={first_id},
        custom_sections=(),
    )
    assert result["department"] == framework["department"]
    assert result["report_mode"] == framework["report_mode"]
    assert result["cover"] == framework["cover"]
    assert result["schema_version"] == framework["schema_version"]
