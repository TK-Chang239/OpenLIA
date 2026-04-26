"""Type round-trips and validation for connector value objects."""

from __future__ import annotations

import pytest
from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    MCPLaunchSpec,
    ScopedBy,
    ScopedTool,
    ToolDefinition,
)


def test_category_values():
    assert {c.value for c in Category} == {"financial", "news", "social", "web_search"}


def test_connector_source_values():
    assert {s.value for s in ConnectorSource} == {"built_in", "remote_mcp", "cli_mcp"}


def test_connector_status_values():
    assert {s.value for s in ConnectorStatus} == {"pending", "validated", "failed"}


def test_scoped_by_values():
    assert {s.value for s in ScopedBy} == {"built_in_map", "llm_adapter"}


def test_mcp_launch_spec_remote_round_trip():
    spec = MCPLaunchSpec.remote(
        url="https://x.example/mcp", headers={"Authorization": "Bearer abc"}
    )
    raw = spec.to_json()
    assert raw == {
        "kind": "remote_mcp",
        "url": "https://x.example/mcp",
        "headers": {"Authorization": "Bearer abc"},
    }
    assert MCPLaunchSpec.from_json(raw) == spec


def test_mcp_launch_spec_cli_round_trip():
    spec = MCPLaunchSpec.cli(argv=["uvx", "some-mcp"], env={"FOO": "BAR"})
    raw = spec.to_json()
    assert raw["kind"] == "cli_mcp"
    assert MCPLaunchSpec.from_json(raw) == spec


def test_mcp_launch_spec_built_in_round_trip():
    spec = MCPLaunchSpec.built_in(template_id="eodhd")
    raw = spec.to_json()
    assert raw == {"kind": "built_in", "template_id": "eodhd"}
    assert MCPLaunchSpec.from_json(raw) == spec


def test_mcp_launch_spec_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown kind"):
        MCPLaunchSpec.from_json({"kind": "ftp", "url": "x"})


@pytest.mark.parametrize(
    "raw,fragment",
    [
        ({"kind": "remote_mcp"}, "missing 'url'"),
        ({"kind": "cli_mcp"}, "missing 'argv'"),
        ({"kind": "built_in"}, "missing 'template_id'"),
    ],
)
def test_mcp_launch_spec_missing_required_field(raw, fragment):
    with pytest.raises(ValueError, match=fragment):
        MCPLaunchSpec.from_json(raw)


def test_tool_definition_keeps_input_schema():
    td = ToolDefinition(
        name="get_quote",
        description="Fetch quote",
        input_schema={"type": "object", "properties": {"ticker": {"type": "string"}}},
    )
    assert td.input_schema["properties"]["ticker"]["type"] == "string"


def test_scoped_tool_is_hashable():
    a = ScopedTool(connector_id="c", tool_name="t", department_id="d")
    b = ScopedTool(connector_id="c", tool_name="t", department_id="d")
    assert {a, b} == {a}
