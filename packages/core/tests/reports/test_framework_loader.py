import pytest
from openlia.reports.frameworks.loader import (
    CustomizationOptions,
    FrameworkNotFoundError,
    load_framework,
    load_style_guide,
)


def test_load_known_framework_returns_dict_with_sections():
    fw = load_framework("stock_initiation")
    assert isinstance(fw, dict)
    assert "sections" in fw
    assert isinstance(fw["sections"], list)
    assert len(fw["sections"]) >= 1


def test_load_unknown_framework_raises():
    with pytest.raises(FrameworkNotFoundError):
        load_framework("nonexistent_framework")


def test_load_style_guide_returns_markdown_string():
    s = load_style_guide("stock_initiation")
    assert isinstance(s, str)
    assert len(s) > 0


def test_customization_disables_sections():
    fw = load_framework("stock_initiation")
    # get first section id to disable
    first_id = fw["sections"][0]["id"]
    fw2 = load_framework(
        "stock_initiation",
        customizations=CustomizationOptions(disabled_section_ids=frozenset({first_id})),
    )
    ids = {s["id"] for s in fw2["sections"]}
    assert first_id not in ids


def test_customization_reorders_sections():
    fw = load_framework("stock_initiation")
    first_id = fw["sections"][0]["id"]
    reordered = load_framework(
        "stock_initiation",
        customizations=CustomizationOptions(
            section_order=[first_id],
        ),
    )
    assert reordered["sections"][0]["id"] == first_id
    assert len(reordered["sections"]) == 1


def test_custom_sections_are_appended():
    custom = {
        "id": "my_section",
        "title": "My Section",
        "instructions": "Custom instructions",
        "blocks": [],
    }
    fw = load_framework(
        "stock_initiation",
        customizations=CustomizationOptions(custom_sections=[custom]),
    )
    ids = [s["id"] for s in fw["sections"]]
    assert ids[-1] == "my_section"
