"""V2 validation: list_tools then optional canary call.

See spec §5 Stage 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.mcp_transport import MCPTransport, SessionFactory
from openlia.connectors.types import MCPLaunchSpec, ToolDefinition


@dataclass(frozen=True)
class ValidationOk:
    tools: list[ToolDefinition]


@dataclass(frozen=True)
class ValidationFailure:
    error: str


ValidationResult = ValidationOk | ValidationFailure


async def validate_connector(
    spec: MCPLaunchSpec,
    canary_tool: str | None,
    session_factory: SessionFactory,
) -> ValidationResult:
    transport = MCPTransport(spec=spec, session_factory=session_factory)
    try:
        await transport.open()
    except Exception as exc:
        return ValidationFailure(error=f"open failed: {exc}")
    try:
        try:
            tools = await transport.list_tools()
        except Exception as exc:
            return ValidationFailure(error=f"list_tools failed: {exc}")
        if canary_tool is not None:
            try:
                await transport.call_tool(canary_tool, {})
            except Exception as exc:
                return ValidationFailure(error=f"canary call '{canary_tool}' failed: {exc}")
        return ValidationOk(tools=tools)
    finally:
        try:
            await transport.close()
        except Exception:
            # close errors must not mask the real result
            pass
