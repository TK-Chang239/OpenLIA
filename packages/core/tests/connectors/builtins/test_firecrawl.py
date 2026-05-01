"""Built-in Firecrawl template tests."""

from __future__ import annotations

from openlia.connectors.builtins.firecrawl import FIRECRAWL_TEMPLATE
from openlia.connectors.builtins.types import RemoteMcpRecipe
from openlia.connectors.types import Category


def test_firecrawl_template_id_and_category() -> None:
    assert FIRECRAWL_TEMPLATE.template_id == "firecrawl"
    assert FIRECRAWL_TEMPLATE.category == Category.WEB_SEARCH
    assert FIRECRAWL_TEMPLATE.api_key_env_var == "FIRECRAWL_API_KEY"


def test_firecrawl_template_has_remote_mcp_mode() -> None:
    modes = FIRECRAWL_TEMPLATE.available_modes
    assert len(modes) >= 1
    assert any(isinstance(m, RemoteMcpRecipe) for m in modes)


def test_firecrawl_runner_specs_cover_world_order_needs() -> None:
    need_ids = {spec.need_id for spec in FIRECRAWL_TEMPLATE.runner_specs}
    assert need_ids == {
        "usd_fx_reserve_share",
        "cb_gold_purchases",
        "foreign_treasury_holdings",
    }


def test_firecrawl_runner_specs_use_firecrawl_extract() -> None:
    for spec in FIRECRAWL_TEMPLATE.runner_specs:
        assert spec.access_mode == "remote_mcp"
        assert spec.tool_name == "firecrawl_extract"
        assert len(spec.result_path) >= 1
        assert "urls" in spec.constants
        assert isinstance(spec.constants["urls"], list)
        assert all(u.startswith("https://") for u in spec.constants["urls"])


def test_firecrawl_canary_tool_is_extract() -> None:
    assert FIRECRAWL_TEMPLATE.canary_tool == "firecrawl_extract"
