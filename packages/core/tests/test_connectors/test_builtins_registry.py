"""Built-in registry has the day-1 catalog and exposes lookups."""

from __future__ import annotations

import pytest
from openlia.connectors.builtins import (
    BuiltInTemplate,
    get_builtin,
    list_builtins_for_category,
)
from openlia.connectors.types import Category


def test_day1_catalog_has_three_entries():
    fin = list_builtins_for_category(Category.FINANCIAL)
    news = list_builtins_for_category(Category.NEWS)
    assert sorted(t.template_id for t in fin) == ["eodhd", "fmp"]
    assert [t.template_id for t in news] == ["newsapi_ai"]
    assert list_builtins_for_category(Category.SOCIAL) == []
    assert list_builtins_for_category(Category.WEB_SEARCH) == []


def test_get_builtin_returns_template():
    t = get_builtin("eodhd")
    assert isinstance(t, BuiltInTemplate)
    assert t.category is Category.FINANCIAL
    assert t.canary_tool
    assert t.api_key_env_var
    assert t.shipped_allowlist
    assert "equity_research" in {a.department_id for a in t.shipped_allowlist}


def test_get_builtin_unknown():
    with pytest.raises(KeyError):
        get_builtin("does_not_exist")


def test_register_rejects_duplicate():
    from openlia.connectors.builtins import register
    from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment

    dup = BuiltInTemplate(
        template_id="eodhd",  # already registered at module import
        display_name="dup",
        category=Category.FINANCIAL,
        api_key_env_var="X",
        cli_argv=("uvx", "x"),
        canary_tool="y",
        shipped_allowlist=(ShippedAssignment("equity_research", "z"),),
    )
    with pytest.raises(ValueError, match="duplicate built-in"):
        register(dup)
