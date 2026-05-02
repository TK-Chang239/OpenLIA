"""Built-in EODHD template tests."""

from __future__ import annotations

from openlia.connectors.builtins.eodhd import EODHD_TEMPLATE
from openlia.connectors.builtins.types import CliMcpRecipe, PythonLibRecipe
from openlia.connectors.types import Category


def test_eodhd_template_id_and_category() -> None:
    assert EODHD_TEMPLATE.template_id == "eodhd"
    assert EODHD_TEMPLATE.category == Category.FINANCIAL
    assert EODHD_TEMPLATE.api_key_env_var == "EODHD_API_KEY"


def test_eodhd_has_both_cli_mcp_and_python_lib_modes() -> None:
    modes = EODHD_TEMPLATE.available_modes
    assert any(isinstance(m, CliMcpRecipe) for m in modes), "expected CLI MCP mode"
    assert any(isinstance(m, PythonLibRecipe) for m in modes), "expected python_lib mode"


def test_eodhd_python_lib_recipe_uses_api_key_env_placeholder() -> None:
    py = next(m for m in EODHD_TEMPLATE.available_modes if isinstance(m, PythonLibRecipe))
    assert py.pip_name == "eodhd"
    assert py.import_module == "eodhd"
    args = dict(py.instance_factory_args)
    assert args.get("api_key") == "$EODHD_API_KEY"


def test_eodhd_runner_specs_cover_expected_needs() -> None:
    """EODHD covers the macro indicators its catalog actually exposes.

    `interest_revenue`, `cpi_core_yoy`, and `pmi` are NOT in EODHD's
    macro-indicators catalog — those needs are covered by FMP only.
    """
    need_ids = {spec.need_id for spec in EODHD_TEMPLATE.runner_specs}
    assert need_ids == {
        "debt_gdp",
        "gdp_yoy",
        "cpi_yoy",
        "stock_quote",
        "social_posts",
    }


def test_eodhd_runner_specs_have_python_lib_or_mcp_access_mode() -> None:
    for spec in EODHD_TEMPLATE.runner_specs:
        assert spec.access_mode in ("python_lib", "cli_mcp", "remote_mcp")
        if spec.access_mode == "python_lib":
            assert spec.module == "eodhd"
            assert spec.method is not None
            assert spec.instance_factory is not None
            assert spec.instance_factory.cls == "APIClient"
            assert spec.instance_factory.args.get("api_key") == "$EODHD_API_KEY"


def test_eodhd_canary_tool_is_set() -> None:
    assert EODHD_TEMPLATE.canary_tool is not None
