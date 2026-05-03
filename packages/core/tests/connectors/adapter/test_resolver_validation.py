"""Tests for the Phase 6 validation gate (`validate_resolved_spec`).

Validates a `CallableSpec` produced by `resolve_user_picked_spec`:
- transforms must be in the extended ALLOWED_TRANSFORMS
- field_map keys must cover the need's canonical_keys (when populated)
- field_map is forbidden on non-list[dict] shapes
- empty field_map is valid only when the endpoint already returns
  canonical-keyed items
"""

from __future__ import annotations

import pytest
from openlia.connectors.adapter.validation import (
    ValidationError,
    validate_resolved_spec,
)
from openlia.connectors.types import (
    ALLOWED_TRANSFORMS,
    CallableSpec,
    NeedParameter,
    ParamBinding,
    RunnerNeed,
)


def _scalar_need() -> RunnerNeed:
    return RunnerNeed(
        id="stock_quote",
        description="quote",
        parameters=[NeedParameter(name="ticker", description="t", type="str", required=True)],
        shape="float",
    )


def _list_dict_need() -> RunnerNeed:
    return RunnerNeed(
        id="geopolitical_news",
        description="news",
        parameters=[],
        shape="list[dict]",
        canonical_keys={
            "title": "str",
            "url": "str",
            "source": "str",
            "published_at": "str",
            "summary": "str",
        },
    )


def _scalar_spec(*, transform: str | None = None) -> CallableSpec:
    return CallableSpec(
        need_id="stock_quote",
        access_mode="remote_mcp",
        tool_name="quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol", transform=transform)},
        constants={},
        shape="float",
    )


def _list_spec(
    *,
    field_map: dict[str, str | tuple[str, ...]] | None = None,
) -> CallableSpec:
    return CallableSpec(
        need_id="geopolitical_news",
        access_mode="python_lib",
        method="X.headlines",
        param_bindings={},
        constants={},
        shape="list[dict]",
        field_map=field_map,
    )


# --------------------------- transforms --------------------------------------


def test_validation_rejects_unknown_transform() -> None:
    spec = _scalar_spec(transform="to_uppercase")
    with pytest.raises(ValidationError, match="to_uppercase"):
        validate_resolved_spec(spec=spec, need=_scalar_need())


@pytest.mark.parametrize("name", ["to_float", "to_int", "strip", "list_first", "iso_date"])
def test_validation_accepts_extended_allowlist(name: str) -> None:
    """Phase 6 extends ALLOWED_TRANSFORMS with five new entries."""
    assert name in ALLOWED_TRANSFORMS
    spec = _scalar_spec(transform=name)
    # Must not raise.
    validate_resolved_spec(spec=spec, need=_scalar_need())


# --------------------------- field_map ---------------------------------------


def test_validation_rejects_field_map_missing_canonical_key() -> None:
    spec = _list_spec(field_map={"title": "title", "url": "url"})  # missing 3 keys
    with pytest.raises(ValidationError, match="canonical"):
        validate_resolved_spec(spec=spec, need=_list_dict_need())


def test_validation_rejects_field_map_for_scalar_shape() -> None:
    spec = CallableSpec(
        need_id="stock_quote",
        access_mode="remote_mcp",
        tool_name="quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol")},
        constants={},
        shape="float",
        field_map={"x": "y"},  # invalid for scalar shape
    )
    with pytest.raises(ValidationError, match="field_map"):
        validate_resolved_spec(spec=spec, need=_scalar_need())


def test_validation_passes_with_empty_field_map_when_keys_already_match() -> None:
    """`{}` means the endpoint already returns canonical-keyed items."""
    spec = _list_spec(field_map={})
    # Empty map with canonical_keys present must FAIL — runtime would not
    # cover the canonical contract. Only valid when canonical_keys is None
    # (which the loader prevents for list[dict]). Per the design doc,
    # empty {} is the "no rename" sentinel: the endpoint already emits
    # canonical names. Validation accepts it; runtime smoke (Phase 7)
    # is the actual check.
    validate_resolved_spec(spec=spec, need=_list_dict_need())


def test_validation_passes_when_field_map_covers_all_canonical_keys() -> None:
    spec = _list_spec(
        field_map={
            "title": "title",
            "url": "url",
            "source": "source",
            "published_at": "published_at",
            "summary": "summary",
        }
    )
    validate_resolved_spec(spec=spec, need=_list_dict_need())


def test_validation_rejects_non_list_dict_with_field_map() -> None:
    """A spec marked `shape='dict'` with field_map should fail (only list[dict])."""
    spec = CallableSpec(
        need_id="x",
        access_mode="remote_mcp",
        tool_name="t",
        shape="dict",
        field_map={"a": "b"},
    )
    need = RunnerNeed(id="x", description="d", parameters=[], shape="dict")
    with pytest.raises(ValidationError, match="field_map"):
        validate_resolved_spec(spec=spec, need=need)
