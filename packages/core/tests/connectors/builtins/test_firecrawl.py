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


def test_firecrawl_has_no_runner_specs() -> None:
    """All previous MR/RS runner specs were removed — Firecrawl is now
    chat-toolbox only (firecrawl_search / firecrawl_scrape for chat depts).
    """
    assert FIRECRAWL_TEMPLATE.runner_specs == ()


def test_firecrawl_canary_tool_is_scrape() -> None:
    """scrape is the modern v2 entrypoint; firecrawl_extract is deprecated."""
    assert FIRECRAWL_TEMPLATE.canary_tool == "scrape"
