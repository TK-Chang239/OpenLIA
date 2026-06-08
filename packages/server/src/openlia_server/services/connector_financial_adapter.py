"""Bridge the connector Dispatcher into the simple ``fetch(need_id, params)``
contract the portfolio price layer expects.

The portfolio code calls ``adapter.fetch("stock_quote", {"ticker": "AAPL"})``
and reads ``result.payload``. We build a fresh ``Dispatcher`` per call so
connector edits land without an app restart, scope it to the department that
owns the need (``stock_quote`` -> ``portfolio``), and wrap the raw
payload in a ``SimpleNamespace`` to match the shape callers expect.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import sessionmaker

from openlia_server.services.connectors_service import _NEED_DEPARTMENT_MAP
from openlia_server.services.dispatcher_factory import build_dispatcher


class ConnectorFinancialAdapter:
    def __init__(self, session_factory: sessionmaker[Any]) -> None:
        self._factory = session_factory

    async def fetch(self, need_id: str, params: dict[str, Any]) -> SimpleNamespace:
        dept = _NEED_DEPARTMENT_MAP.get(need_id)
        if dept is None:
            raise ValueError(f"unknown need_id {need_id!r}")
        with self._factory() as session:
            dispatcher = build_dispatcher(session)
            async with dispatcher.in_department(dept):
                payload = await dispatcher.fetch_need(need_id, **params)
        return SimpleNamespace(payload=payload)
