"""Tests for v2 connector value types."""

from __future__ import annotations

import dataclasses

import pytest
from openlia.connectors.types import (
    ALLOWED_TRANSFORMS,
    TRANSFORMS,
    CallableDefinition,
    CallableSpec,
    Category,
    CliMcpMode,
    ConnectorSource,
    ConnectorStatus,
    InstanceFactory,
    LaunchSpec,
    NeedParameter,
    ParamBinding,
    PythonLibMode,
    RemoteMcpMode,
    RunnerNeed,
    ToolDefinition,
)


def test_category_values() -> None:
    assert {c.value for c in Category} == {"financial", "news", "social", "web_search"}


def test_connector_source_values() -> None:
    assert {s.value for s in ConnectorSource} == {
        "built_in",
        "remote_mcp",
        "cli_mcp",
        "python_lib",
        "skill",
    }


def test_connector_status_values() -> None:
    assert {s.value for s in ConnectorStatus} == {"pending", "validated", "failed"}


def test_cli_mcp_mode_is_frozen() -> None:
    mode = CliMcpMode(kind="cli_mcp", argv=["uvx", "some-mcp"], env_keys=["FOO"])
    with pytest.raises(dataclasses.FrozenInstanceError):
        mode.argv = []  # type: ignore[misc]


def test_remote_mcp_mode_is_frozen() -> None:
    mode = RemoteMcpMode(kind="remote_mcp", url="https://x.example/mcp", headers={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        mode.url = "y"  # type: ignore[misc]


def test_python_lib_mode_is_frozen() -> None:
    mode = PythonLibMode(
        kind="python_lib",
        pip_name="eodhd",
        pip_version="1.0.0",
        import_module="eodhd",
        instance_factory=InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"}),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        mode.pip_name = "x"  # type: ignore[misc]


def test_instance_factory_is_frozen() -> None:
    factory = InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        factory.cls = "Other"  # type: ignore[misc]


def test_launch_spec_holds_multiple_modes() -> None:
    cli = CliMcpMode(kind="cli_mcp", argv=["uvx", "eodhd-mcp"], env_keys=["EODHD_API_KEY"])
    lib = PythonLibMode(
        kind="python_lib",
        pip_name="eodhd",
        pip_version="1.0.0",
        import_module="eodhd",
        instance_factory=InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"}),
    )
    spec = LaunchSpec(modes=[cli, lib])
    assert len(spec.modes) == 2
    assert spec.modes[0] is cli
    assert spec.modes[1] is lib


def test_tool_definition_keeps_input_schema() -> None:
    td = ToolDefinition(
        name="get_quote",
        description="Fetch quote",
        input_schema={"type": "object", "properties": {"ticker": {"type": "string"}}},
    )
    assert td.input_schema["properties"]["ticker"]["type"] == "string"


def test_callable_definition_is_frozen() -> None:
    cd = CallableDefinition(
        qualname="APIClient.real_time_quote",
        signature="(symbol: str) -> dict",
        doc="Fetch latest quote.",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        cd.qualname = "Other"  # type: ignore[misc]


def test_runner_need_is_frozen() -> None:
    need = RunnerNeed(
        id="quote",
        description="Latest price",
        parameters=[
            NeedParameter(name="symbol", description="Ticker", type="str", required=True),
        ],
        shape="float",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        need.id = "other"  # type: ignore[misc]


def test_need_parameter_default_none() -> None:
    p = NeedParameter(name="symbol", description="Ticker", type="str", required=True)
    assert p.default is None


def test_param_binding_default_transform_none() -> None:
    b = ParamBinding(to_arg="symbol")
    assert b.transform is None


def test_callable_spec_mcp_shape() -> None:
    spec = CallableSpec(
        need_id="quote",
        access_mode="cli_mcp",
        tool_name="get_real_time_quote",
        param_bindings={"symbol": ParamBinding(to_arg="ticker", transform="upper")},
        shape="float",
    )
    assert spec.access_mode == "cli_mcp"
    assert spec.module is None
    assert spec.method is None
    assert spec.tool_name == "get_real_time_quote"
    assert spec.param_bindings["symbol"].transform == "upper"


def test_callable_spec_python_lib_shape() -> None:
    spec = CallableSpec(
        need_id="quote",
        access_mode="python_lib",
        module="eodhd",
        instance_factory=InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"}),
        method="real_time_quote",
        shape="dict",
    )
    assert spec.access_mode == "python_lib"
    assert spec.tool_name is None
    assert spec.method == "real_time_quote"
    assert spec.constants == {}


def test_callable_spec_defaults_independent() -> None:
    a = CallableSpec(need_id="a", access_mode="cli_mcp")
    b = CallableSpec(need_id="b", access_mode="cli_mcp")
    a.param_bindings["x"] = ParamBinding(to_arg="x")
    assert b.param_bindings == {}


def test_transforms_registry_keys() -> None:
    assert {"upper", "lower", "iso_to_eodhd"} <= set(TRANSFORMS.keys())
    assert ALLOWED_TRANSFORMS == frozenset(TRANSFORMS.keys())


def test_transforms_callable() -> None:
    assert TRANSFORMS["upper"]("aapl") == "AAPL"
    assert TRANSFORMS["lower"]("AAPL") == "aapl"
    assert TRANSFORMS["iso_to_eodhd"]("AAPL") == "AAPL.NYSE"


def test_callable_spec_result_path_default_is_empty_tuple() -> None:
    spec = CallableSpec(need_id="x", access_mode="cli_mcp", tool_name="t")
    assert spec.result_path == ()


def test_callable_spec_result_path_accepts_tuple() -> None:
    spec = CallableSpec(
        need_id="x",
        access_mode="remote_mcp",
        tool_name="firecrawl_extract",
        result_path=("data", "usd_share_pct"),
    )
    assert spec.result_path == ("data", "usd_share_pct")
