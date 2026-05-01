"""Built-in registry shape tests.

Day-1 catalog is locked empty per spec §13.5; these tests pin the shape
of the registry, not specific templates.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from openlia.connectors.builtins import (
    BUILTIN_TEMPLATES,
    BuiltInTemplate,
    CliMcpRecipe,
    PythonLibRecipe,
    RemoteMcpRecipe,
    get_template,
    list_templates,
)
from openlia.connectors.types import Category


def test_builtin_templates_is_empty_tuple() -> None:
    assert BUILTIN_TEMPLATES == ()
    assert isinstance(BUILTIN_TEMPLATES, tuple)


def test_list_templates_returns_empty_tuple() -> None:
    result = list_templates()
    assert result == ()
    assert isinstance(result, tuple)


def test_get_template_unknown_returns_none() -> None:
    assert get_template("anything") is None
    assert get_template("eodhd") is None
    assert get_template("") is None


def test_builtin_template_is_frozen() -> None:
    tpl = BuiltInTemplate(
        template_id="x",
        display_name="X",
        category=Category.FINANCIAL,
        api_key_env_var="X_API_KEY",
        available_modes=(),
        canary_tool=None,
    )
    with pytest.raises(FrozenInstanceError):
        tpl.template_id = "y"  # type: ignore[misc]


def test_cli_mcp_recipe_is_frozen_with_kind_literal() -> None:
    recipe = CliMcpRecipe(kind="cli_mcp", argv=("uvx", "thing"), env_keys=("KEY",))
    assert recipe.kind == "cli_mcp"
    with pytest.raises(FrozenInstanceError):
        recipe.kind = "remote_mcp"  # type: ignore[misc]


def test_remote_mcp_recipe_is_frozen_with_kind_literal() -> None:
    recipe = RemoteMcpRecipe(kind="remote_mcp", url="https://x", headers=(("a", "b"),))
    assert recipe.kind == "remote_mcp"
    with pytest.raises(FrozenInstanceError):
        recipe.url = "https://y"  # type: ignore[misc]


def test_python_lib_recipe_is_frozen_with_kind_literal() -> None:
    recipe = PythonLibRecipe(
        kind="python_lib",
        pip_name="foo",
        pip_version="1.0",
        import_module="foo",
        instance_factory_cls="Client",
        instance_factory_args=(("api_key", "$FOO_KEY"),),
    )
    assert recipe.kind == "python_lib"
    with pytest.raises(FrozenInstanceError):
        recipe.pip_name = "bar"  # type: ignore[misc]


def test_builtin_template_runner_specs_default_is_empty_tuple() -> None:
    tpl = BuiltInTemplate(
        template_id="x",
        display_name="X",
        category=Category.SOCIAL,
        api_key_env_var="X_API_KEY",
        available_modes=(),
        canary_tool=None,
    )
    assert tpl.runner_specs == ()


def test_builtin_template_runner_specs_accepts_tuple() -> None:
    from openlia.connectors.types import CallableSpec

    spec = CallableSpec(need_id="n", access_mode="remote_mcp", tool_name="t")
    tpl = BuiltInTemplate(
        template_id="x",
        display_name="X",
        category=Category.NEWS,
        api_key_env_var="X_API_KEY",
        available_modes=(),
        canary_tool=None,
        runner_specs=(spec,),
    )
    assert tpl.runner_specs == (spec,)


def test_recipes_are_hashable() -> None:
    cli = CliMcpRecipe(kind="cli_mcp", argv=("uvx", "x"), env_keys=("K",))
    remote = RemoteMcpRecipe(kind="remote_mcp", url="https://x", headers=(("a", "b"),))
    py = PythonLibRecipe(
        kind="python_lib",
        pip_name="foo",
        pip_version="1.0",
        import_module="foo",
        instance_factory_cls="Client",
        instance_factory_args=(("k", "v"),),
    )
    # Hashability sanity check: must work in a set.
    assert len({cli, remote, py}) == 3
