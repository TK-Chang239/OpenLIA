"""Built-in FMP template tests."""

from __future__ import annotations

from openlia.connectors.builtins.fmp import FMP_TEMPLATE
from openlia.connectors.builtins.types import PythonLibRecipe
from openlia.connectors.types import Category


def test_fmp_template_id_and_category() -> None:
    assert FMP_TEMPLATE.template_id == "fmp"
    assert FMP_TEMPLATE.category == Category.FINANCIAL
    assert FMP_TEMPLATE.api_key_env_var == "FMP_API_KEY"


def test_fmp_has_python_lib_mode() -> None:
    modes = FMP_TEMPLATE.available_modes
    assert any(isinstance(m, PythonLibRecipe) for m in modes), "expected python_lib mode"


def test_fmp_python_lib_recipe_pip_name_is_fmpsdk() -> None:
    py = next(m for m in FMP_TEMPLATE.available_modes if isinstance(m, PythonLibRecipe))
    assert py.pip_name == "fmpsdk"
    assert py.import_module == "fmpsdk"


def test_fmp_runner_specs_cover_expected_needs() -> None:
    need_ids = {spec.need_id for spec in FMP_TEMPLATE.runner_specs}
    expected = {
        "debt_gdp",
        "interest_revenue",
        "gdp_yoy",
        "cpi_yoy",
        "cpi_core_yoy",
        "pmi",
        "stock_quote",
        "social_posts",
    }
    # Same coverage assertion as EODHD: at least 6 of 8.
    assert len(expected & need_ids) >= 6, (
        f"FMP must cover most expected needs; missing: {expected - need_ids}"
    )


def test_fmp_canary_tool_is_set() -> None:
    assert FMP_TEMPLATE.canary_tool is not None
