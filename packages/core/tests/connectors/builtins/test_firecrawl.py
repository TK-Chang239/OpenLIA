"""Built-in Firecrawl template tests."""

from __future__ import annotations

from openlia.connectors.builtins.firecrawl import FIRECRAWL_TEMPLATE
from openlia.connectors.builtins.types import (
    CliMcpRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
)
from openlia.connectors.types import Category


def test_firecrawl_template_id_and_category() -> None:
    assert FIRECRAWL_TEMPLATE.template_id == "firecrawl"
    assert FIRECRAWL_TEMPLATE.category == Category.WEB_SEARCH
    assert FIRECRAWL_TEMPLATE.api_key_env_var == "FIRECRAWL_API_KEY"


def test_firecrawl_template_has_python_lib_remote_and_cli_modes() -> None:
    modes = FIRECRAWL_TEMPLATE.available_modes
    assert any(isinstance(m, PythonLibRecipe) for m in modes)
    assert any(isinstance(m, RemoteMcpRecipe) for m in modes)
    assert any(isinstance(m, CliMcpRecipe) for m in modes)


def test_firecrawl_python_lib_targets_firecrawl_py_sdk() -> None:
    py_modes = [m for m in FIRECRAWL_TEMPLATE.available_modes if isinstance(m, PythonLibRecipe)]
    assert len(py_modes) == 1
    py = py_modes[0]
    assert py.pip_name == "firecrawl-py"
    assert py.import_module == "firecrawl"
    assert py.instance_factory_cls == "Firecrawl"
    # api_key arg references the env var via $-prefix placeholder
    assert ("api_key", "$FIRECRAWL_API_KEY") in py.instance_factory_args


def test_firecrawl_remote_mcp_uses_v2_mcp_path_with_substitution_placeholder() -> None:
    """The placeholder is keyed by the env-var name so dispatcher_factory's
    `_substitute_secrets` can fill it in at install time.
    """
    remote = next(m for m in FIRECRAWL_TEMPLATE.available_modes if isinstance(m, RemoteMcpRecipe))
    assert remote.url == "https://mcp.firecrawl.dev/{FIRECRAWL_API_KEY}/v2/mcp"


def test_firecrawl_runner_specs_cover_world_order_and_interest_revenue_needs() -> None:
    """Firecrawl handles the four needs no upstream financial API exposes:
    three world-order needs (USD reserve share, central-bank gold purchases,
    foreign Treasury holdings) plus interest_revenue (federal interest
    expense as % of revenue).
    """
    need_ids = {spec.need_id for spec in FIRECRAWL_TEMPLATE.runner_specs}
    assert need_ids == {
        "usd_fx_reserve_share",
        "cb_gold_purchases",
        "foreign_treasury_holdings",
        "interest_revenue",
    }


def test_firecrawl_runner_specs_use_python_lib_scrape() -> None:
    """Specs target SDK scrape with v2 JSON-mode formats; deprecated /extract avoided."""
    for spec in FIRECRAWL_TEMPLATE.runner_specs:
        assert spec.access_mode == "python_lib"
        assert spec.method == "Firecrawl.scrape"
        assert spec.tool_name is None
        # result_path walks into the Document.json field then into the schema key
        assert len(spec.result_path) == 2
        assert spec.result_path[0] == "json"
        # constants carry a single URL and v2 JSON-mode formats array
        assert "url" in spec.constants
        assert spec.constants["url"].startswith("https://")
        formats = spec.constants["formats"]
        assert isinstance(formats, list) and len(formats) == 1
        assert formats[0]["type"] == "json"
        assert "schema" in formats[0]
        # the schema's required field matches the second result_path segment
        required = formats[0]["schema"]["required"]
        assert spec.result_path[1] in required


def test_firecrawl_canary_tool_is_scrape() -> None:
    """scrape is the modern v2 entrypoint; firecrawl_extract is deprecated."""
    assert FIRECRAWL_TEMPLATE.canary_tool == "scrape"


def test_firecrawl_runner_spec_urls_were_live_verified() -> None:
    """URLs were probed against the real Firecrawl scrape endpoint
    (2026-05-01) using the user's API key. Each one returns a sensible
    non-zero number under JSON mode with our schema. URLs in this test
    are pinned so a refactor can't accidentally regress the source.
    """
    by_need = {spec.need_id: spec for spec in FIRECRAWL_TEMPLATE.runner_specs}
    assert by_need["usd_fx_reserve_share"].constants["url"] == (
        "https://en.wikipedia.org/wiki/Reserve_currency"
    )
    assert by_need["cb_gold_purchases"].constants["url"] == (
        "https://www.gold.org/goldhub/research/gold-demand-trends/"
        "gold-demand-trends-full-year-2024"
    )
    assert by_need["foreign_treasury_holdings"].constants["url"] == (
        "https://ticdata.treasury.gov/Publish/mfh.txt"
    )
    assert by_need["interest_revenue"].constants["url"] == (
        "https://en.wikipedia.org/wiki/National_debt_of_the_United_States"
    )


def test_foreign_treasury_holdings_field_is_total_not_change() -> None:
    """Live source publishes the absolute total ($ billions), not a
    trailing-Δ. The need shape changed accordingly; document it here.
    """
    spec = next(
        s for s in FIRECRAWL_TEMPLATE.runner_specs if s.need_id == "foreign_treasury_holdings"
    )
    schema = spec.constants["formats"][0]["schema"]
    assert "total_usd_billions" in schema["properties"]
    assert spec.result_path == ("json", "total_usd_billions")
