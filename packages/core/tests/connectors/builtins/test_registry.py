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


def test_runner_specs_reference_only_declared_need_ids() -> None:
    """Every runner_spec's need_id must appear in some department's needs.yaml."""
    from pathlib import Path

    import yaml

    needs_dir = Path(__file__).resolve().parents[3] / "src" / "openlia" / "departments"
    declared: set[str] = set()
    for yaml_path in needs_dir.glob("*.needs.yaml"):
        data = yaml.safe_load(yaml_path.read_text())
        for need in data.get("needs", []):
            declared.add(need["id"])

    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            assert spec.need_id in declared, (
                f"template {tpl.template_id!r} references unknown need {spec.need_id!r}"
            )


def _load_canonical_keys_by_need_id() -> dict[str, dict[str, str]]:
    """Build {need_id: canonical_keys} from all departments' needs.yaml files.

    Mirrors how the loader parses needs, but lighter — we only need the
    canonical_keys map for cross-checking catalog field_maps.
    """
    from pathlib import Path

    import yaml

    needs_dir = Path(__file__).resolve().parents[3] / "src" / "openlia" / "departments"
    out: dict[str, dict[str, str]] = {}
    for yaml_path in needs_dir.glob("*.needs.yaml"):
        data = yaml.safe_load(yaml_path.read_text())
        for need in data.get("needs", []):
            ck = need.get("canonical_keys")
            if isinstance(ck, dict):
                out[need["id"]] = {str(k): str(v) for k, v in ck.items()}
    return out


def test_every_list_dict_runner_spec_has_field_map() -> None:
    """Phase 4 invariant: catalog list[dict] specs must declare a field_map.

    `field_map = None` means "not declared" and is invalid for list[dict]
    shapes. `field_map = {}` is valid (means the endpoint already returns
    canonical keys) when canonical_keys is empty; otherwise the spec must
    populate the rename map.
    """
    canonical = _load_canonical_keys_by_need_id()
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            if spec.shape != "list[dict]":
                continue
            assert spec.field_map is not None, (
                f"template {tpl.template_id!r} spec for need {spec.need_id!r} "
                f"is shape 'list[dict]' but does not declare field_map"
            )
            need_keys = canonical.get(spec.need_id, {})
            if need_keys:
                assert spec.field_map, (
                    f"template {tpl.template_id!r} spec for need {spec.need_id!r} "
                    f"has empty field_map but the need declares canonical_keys "
                    f"{set(need_keys)}; the catalog must populate the rename map."
                )


def test_field_maps_cover_canonical_keys() -> None:
    """Phase 4 invariant: catalog field_map keys must cover the need's canonical_keys."""
    canonical = _load_canonical_keys_by_need_id()
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            if spec.shape != "list[dict]":
                continue
            need_keys = set(canonical.get(spec.need_id, {}).keys())
            if not need_keys:
                continue
            fm = spec.field_map or {}
            missing = need_keys - set(fm.keys())
            assert not missing, (
                f"template {tpl.template_id!r} spec for need {spec.need_id!r} "
                f"field_map {set(fm)} missing canonical keys: {missing}"
            )


def test_every_runner_need_is_covered_by_at_least_one_template() -> None:
    """Every declared need (across both runner depts) is covered by at least one builtin."""
    from pathlib import Path

    import yaml

    needs_dir = Path(__file__).resolve().parents[3] / "src" / "openlia" / "departments"
    declared: set[str] = set()
    for yaml_path in needs_dir.glob("*.needs.yaml"):
        data = yaml.safe_load(yaml_path.read_text())
        for need in data.get("needs", []):
            declared.add(need["id"])

    covered: set[str] = set()
    for tpl in BUILTIN_TEMPLATES:
        for spec in tpl.runner_specs:
            covered.add(spec.need_id)

    missing = declared - covered
    assert not missing, f"runner needs uncovered by day-1 catalog: {missing}"
