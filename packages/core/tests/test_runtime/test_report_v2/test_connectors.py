from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.connectors.base import (
    ToolMeta,
    ToolResult,
)
from openlia.llm.runtime.report_v2.connectors.registry import (
    get_adapter,
    list_adapters,
    register_adapter,
    reset_registry_for_tests,
)


class FakeAdapter:
    name = "fake"
    tool_kind = "internal"
    cacheable = False

    def list_tools(self) -> list[ToolMeta]:
        return [ToolMeta(name="echo", description="echo input")]

    def call(self, tool: str, params: dict) -> ToolResult:
        return ToolResult(content=params.get("msg", ""), metadata={}, served_from_cache=False)


def test_register_and_lookup():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    a = get_adapter("fake")
    assert a.name == "fake"
    assert a.tool_kind == "internal"


def test_call_returns_tool_result():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    a = get_adapter("fake")
    r = a.call("echo", {"msg": "hi"})
    assert r.content == "hi"
    assert r.served_from_cache is False


def test_register_duplicate_raises():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    with pytest.raises(ValueError):
        register_adapter(FakeAdapter())


def test_list_adapters_returns_all():
    reset_registry_for_tests()
    register_adapter(FakeAdapter())
    assert "fake" in {a.name for a in list_adapters()}
