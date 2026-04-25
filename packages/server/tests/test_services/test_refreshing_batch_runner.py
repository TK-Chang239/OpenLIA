"""NEW-5-06 — RefreshingBatchRunner opens/closes a fresh DB session per `.run()`."""

from __future__ import annotations

import pytest


class _SpySession:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _SpyFactory:
    def __init__(self) -> None:
        self.opened: list[_SpySession] = []

    def __call__(self) -> _SpySession:
        s = _SpySession(f"s_{len(self.opened)}")
        self.opened.append(s)
        return s


@pytest.fixture(autouse=True)
def _fake_inner(monkeypatch):
    from openlia_server.services import runtime as svc

    class _FakeBatchRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run(
            self,
            *,
            department_id,
            task,
            items,
            schema,
            concurrency: int = 8,
            user_id=None,
            cancel_token=None,
        ):
            self.calls += 1
            return [{"id": it.get("id"), "ok": True, "data": {}} for it in items]

    def _fake_build(registry):
        return _FakeBatchRunner()

    monkeypatch.setattr(svc, "_build_batch_runner_with_registry", _fake_build)

    class _NoopRegistry:
        def __init__(self, db) -> None:
            self.db = db

    monkeypatch.setattr(svc, "SQLModelRegistry", _NoopRegistry)


@pytest.mark.asyncio
async def test_build_batch_runner_returns_refreshing_wrapper() -> None:
    from openlia_server.services.runtime import RefreshingBatchRunner, build_batch_runner

    factory = _SpyFactory()
    runner = build_batch_runner(factory)
    assert isinstance(runner, RefreshingBatchRunner)


@pytest.mark.asyncio
async def test_refreshing_batch_runner_opens_and_closes_session_per_run() -> None:
    from openlia_server.services.runtime import build_batch_runner

    factory = _SpyFactory()
    runner = build_batch_runner(factory)

    items = [{"id": "a"}, {"id": "b"}]
    result = await runner.run(
        department_id="retail_sentiment",
        task="classify_sentiment",
        items=items,
        schema=object,
    )

    assert len(result) == 2
    assert len(factory.opened) == 1
    assert factory.opened[0].closed is True


@pytest.mark.asyncio
async def test_refreshing_batch_runner_closes_session_on_inner_exception(monkeypatch) -> None:
    from openlia_server.services import runtime as svc
    from openlia_server.services.runtime import build_batch_runner

    class _BoomBatch:
        async def run(self, **kwargs):
            raise RuntimeError("inner boom")

    monkeypatch.setattr(svc, "_build_batch_runner_with_registry", lambda r: _BoomBatch())

    factory = _SpyFactory()
    runner = build_batch_runner(factory)
    with pytest.raises(RuntimeError, match="inner boom"):
        await runner.run(
            department_id="retail_sentiment",
            task="classify_sentiment",
            items=[],
            schema=object,
        )
    assert factory.opened[0].closed is True
