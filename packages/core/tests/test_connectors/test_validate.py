"""V2 validation: list_tools always; canary call only for built-ins."""

from __future__ import annotations

from openlia.connectors.types import MCPLaunchSpec, ToolDefinition
from openlia.connectors.validate import (
    ValidationFailure,
    ValidationOk,
    validate_connector,
)


class _FakeSession:
    def __init__(
        self,
        tools: list[ToolDefinition],
        call_results: dict[str, object] | None = None,
        list_raises: BaseException | None = None,
        open_raises: BaseException | None = None,
    ) -> None:
        self.tools = tools
        self.call_results = call_results or {}
        self.list_raises = list_raises
        self.open_raises = open_raises
        self.opened = False
        self.closed = False

    async def open(self) -> None:
        if self.open_raises is not None:
            raise self.open_raises
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def list_tools(self) -> list[ToolDefinition]:
        if self.list_raises is not None:
            raise self.list_raises
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict) -> object:
        if name not in self.call_results:
            raise RuntimeError(f"call failed for {name}")
        return self.call_results[name]


async def test_remote_mcp_only_calls_list_tools():
    fake = _FakeSession(tools=[ToolDefinition(name="t", description="", input_schema={})])
    result = await validate_connector(
        spec=MCPLaunchSpec.remote(url="https://x.example/mcp"),
        canary_tool=None,
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationOk)
    assert [t.name for t in result.tools] == ["t"]
    assert fake.closed is True


async def test_built_in_invokes_canary():
    fake = _FakeSession(
        tools=[ToolDefinition(name="get_user_details", description="", input_schema={})],
        call_results={"get_user_details": {"ok": True}},
    )
    result = await validate_connector(
        spec=MCPLaunchSpec.cli(argv=["uvx", "eodhd-mcp"]),
        canary_tool="get_user_details",
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationOk)


async def test_list_tools_failure_returns_validation_failure():
    fake = _FakeSession(tools=[], list_raises=RuntimeError("boom"))
    result = await validate_connector(
        spec=MCPLaunchSpec.remote(url="https://x"),
        canary_tool=None,
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationFailure)
    assert "boom" in result.error
    assert fake.closed is True


async def test_canary_failure_returns_validation_failure():
    fake = _FakeSession(
        tools=[ToolDefinition(name="x", description="", input_schema={})],
        call_results={},
    )
    result = await validate_connector(
        spec=MCPLaunchSpec.cli(argv=["uvx", "x"]),
        canary_tool="ping",
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationFailure)
    assert "ping" in result.error


async def test_open_failure_returns_validation_failure_without_close():
    fake = _FakeSession(tools=[], open_raises=ConnectionError("network down"))
    result = await validate_connector(
        spec=MCPLaunchSpec.remote(url="https://x"),
        canary_tool=None,
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationFailure)
    assert "network down" in result.error
