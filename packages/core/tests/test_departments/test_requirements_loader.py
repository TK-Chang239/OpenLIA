"""Department requirements loader: parses sibling YAML and validates schema."""

from __future__ import annotations

import pytest


def test_loader_reads_sibling_yaml(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    yaml_path = tmp_path / "x.requirements.yaml"
    yaml_path.write_text(
        "financial:\n"
        "  required: true\n"
        "  description: |\n"
        "    Need fundamentals.\n"
        "news:\n"
        "  required: false\n"
        "  description: optional news\n"
    )
    out = load_requirements_yaml(yaml_path)
    assert out["financial"]["required"] is True
    assert "fundamentals" in out["financial"]["description"]
    assert out["news"]["required"] is False


def test_loader_rejects_unknown_category(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    p = tmp_path / "x.requirements.yaml"
    p.write_text("nonsense:\n  required: true\n  description: x\n")
    with pytest.raises(ValueError, match="unknown category"):
        load_requirements_yaml(p)


def test_loader_requires_required_and_description(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    p = tmp_path / "x.requirements.yaml"
    p.write_text("financial:\n  required: true\n")
    with pytest.raises(ValueError, match="description"):
        load_requirements_yaml(p)


def test_loader_rejects_non_bool_required(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    p = tmp_path / "x.requirements.yaml"
    p.write_text("financial:\n  required: yesplease\n  description: x\n")
    with pytest.raises(ValueError, match="bool"):
        load_requirements_yaml(p)


def test_loader_rejects_empty_description(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    p = tmp_path / "x.requirements.yaml"
    p.write_text('financial:\n  required: true\n  description: ""\n')
    with pytest.raises(ValueError, match="description"):
        load_requirements_yaml(p)


def test_get_all_requirements_returns_known_departments():
    """After Phase D YAMLs land, every department class has loadable requirements."""

    from openlia.departments import get_all_requirements

    out = get_all_requirements()
    expected = {
        "secretary",
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "retail_sentiment",
        "macro_research",
        "panic_thermometer",
    }
    assert expected.issubset(out.keys())
    er = out["equity_research"]
    assert "financial" in er.per_category


def test_get_all_requirements_returns_dict_when_no_yamls_yet():
    """Until Phase D2-D8 lands, get_all_requirements returns whatever is there (possibly empty)."""

    from openlia.departments import get_all_requirements

    out = get_all_requirements()
    assert isinstance(out, dict)
