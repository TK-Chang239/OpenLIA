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


def test_get_template_unknown_returns_none() -> None:
    assert get_template("anything") is None
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


def test_builtin_templates_has_six_entries() -> None:
    template_ids = {t.template_id for t in BUILTIN_TEMPLATES}
    assert template_ids == {"eodhd", "fmp", "newsapi_ai", "mediastack", "firecrawl", "x"}


def test_list_templates_returns_six_entries() -> None:
    assert len(list_templates()) == 6


def test_get_template_finds_each_builtin() -> None:
    for tid in ("eodhd", "fmp", "newsapi_ai", "mediastack", "firecrawl", "x"):
        tpl = get_template(tid)
        assert tpl is not None, f"missing template: {tid}"
        assert tpl.template_id == tid


def test_runner_spec_need_ids_are_non_empty() -> None:
    """Every runner spec must have a non-empty need_id string."""
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            assert spec.need_id, f"template {tpl.template_id!r} has a spec with an empty need_id"


def test_every_list_dict_runner_spec_has_field_map_when_non_empty_shape() -> None:
    """Internal-consistency: list[dict] specs must declare a field_map (may be empty dict).

    `field_map = None` means undeclared and is invalid for list[dict] shapes.
    """
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            if spec.shape != "list[dict]":
                continue
            assert spec.field_map is not None, (
                f"template {tpl.template_id!r} spec for need {spec.need_id!r} "
                f"is shape 'list[dict]' but does not declare field_map"
            )


def test_list_dict_runner_spec_field_map_keys_are_non_empty() -> None:
    """Internal-consistency: each field_map key in a list[dict] spec must be a non-empty string."""
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            if spec.shape != "list[dict]" or not spec.field_map:
                continue
            for key in spec.field_map:
                assert key, (
                    f"template {tpl.template_id!r} spec for need {spec.need_id!r} "
                    f"has an empty field_map key"
                )


def test_portfolio_needs_covered_by_at_least_one_template() -> None:
    """The three portfolio runner needs must be covered by at least one builtin."""
    portfolio_needs = {"stock_quote", "eod_history", "company_profile"}
    covered: set[str] = set()
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            covered.add(spec.need_id)
    missing = portfolio_needs - covered
    assert not missing, f"portfolio runner needs uncovered by catalog: {missing}"
