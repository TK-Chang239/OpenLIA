from __future__ import annotations

from openlia.llm.runtime.report_v2.connectors.base import ConnectorAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ConnectorAdapter] = {}

    def register(self, adapter: ConnectorAdapter) -> None:
        if adapter.name in self._adapters:
            raise ValueError(f"adapter {adapter.name!r} already registered")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ConnectorAdapter:
        if name not in self._adapters:
            raise KeyError(f"no adapter registered as {name!r}")
        return self._adapters[name]

    def list(self) -> list[ConnectorAdapter]:
        return list(self._adapters.values())

    def reset(self) -> None:
        self._adapters.clear()


_default = AdapterRegistry()


def register_adapter(a: ConnectorAdapter) -> None:
    _default.register(a)


def get_adapter(name: str) -> ConnectorAdapter:
    return _default.get(name)


def list_adapters() -> list[ConnectorAdapter]:
    return _default.list()


def reset_registry_for_tests() -> None:
    _default.reset()
