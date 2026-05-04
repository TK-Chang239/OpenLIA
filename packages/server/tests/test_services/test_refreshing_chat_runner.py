"""NEW-5-05 — RefreshingChatRunner opens/closes a fresh DB session per `.run()`.

Mirrors the pattern proven by `RefreshingReportRunner`. The test uses a
spy session-factory that records open/close events so we can assert the
session is closed on:
  - normal iterator exhaustion,
  - exception inside the runner,
  - cancellation (the iterator stops without a terminal event).
"""

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
    """Replace `_build_chat_runner_with_registry` with a fake that doesn't
    touch the real LLM admin config or the prompts package."""
    from openlia_server.services import runtime as svc

    class _FakeRunner:
        def __init__(self, label: str) -> None:
            self.label = label
            self.runs = 0

        async def run(
            self,
            *,
            department_id,
            user_id,
            messages,
            attachments=None,
            cancel_token=None,
            **_,
        ):
            self.runs += 1
            yield {"type": "chat.start", "label": self.label, "run": self.runs}
            yield {"type": "chat.done"}

    def _fake_build(registry, *, web_search=None, skill_registry=None):
        return _FakeRunner(label="fake")

    monkeypatch.setattr(svc, "_build_chat_runner_with_registry", _fake_build)

    # Also stub SQLModelRegistry to a no-op constructor.
    class _NoopRegistry:
        def __init__(self, db) -> None:
            self.db = db

    monkeypatch.setattr(svc, "SQLModelRegistry", _NoopRegistry)

    # Skip the real DB-backed search-provider lookup in tests.
    from openlia.llm.runtime.web_search import WebSearchResolution

    monkeypatch.setattr(
        svc,
        "_resolve_configured_search",
        lambda db: WebSearchResolution(available=False, variant=None, adapter=None),
    )


@pytest.mark.asyncio
async def test_refreshing_chat_runner_opens_and_closes_session_on_normal_run() -> None:
    from openlia_server.services.runtime import RefreshingChatRunner

    factory = _SpyFactory()
    runner = RefreshingChatRunner(factory)

    events = []
    async for e in runner.run(department_id="secretary", user_id="u1", messages=[]):
        events.append(e)

    assert len(factory.opened) == 1
    assert factory.opened[0].closed is True
    assert any(e.get("type") == "chat.done" for e in events)


@pytest.mark.asyncio
async def test_refreshing_chat_runner_opens_fresh_session_per_run() -> None:
    from openlia_server.services.runtime import RefreshingChatRunner

    factory = _SpyFactory()
    runner = RefreshingChatRunner(factory)

    async def _drive() -> None:
        async for _ in runner.run(department_id="secretary", user_id="u1", messages=[]):
            pass

    await _drive()
    await _drive()
    await _drive()

    assert len(factory.opened) == 3
    for session in factory.opened:
        assert session.closed is True


@pytest.mark.asyncio
async def test_refreshing_chat_runner_closes_session_on_exception(monkeypatch) -> None:
    from openlia_server.services import runtime as svc
    from openlia_server.services.runtime import RefreshingChatRunner

    class _BoomRunner:
        async def run(self, **kwargs):
            yield {"type": "chat.start"}
            raise RuntimeError("boom")

    monkeypatch.setattr(
        svc,
        "_build_chat_runner_with_registry",
        lambda r, *, web_search=None, skill_registry=None: _BoomRunner(),
    )

    factory = _SpyFactory()
    runner = RefreshingChatRunner(factory)

    with pytest.raises(RuntimeError, match="boom"):
        async for _ in runner.run(department_id="secretary", user_id="u1", messages=[]):
            pass

    assert factory.opened[0].closed is True


@pytest.mark.asyncio
async def test_refreshing_chat_runner_closes_session_on_early_break() -> None:
    """Simulates client-disconnect: caller breaks out of the iterator
    before exhaustion. Explicitly closing the async generator must run
    its `finally` block and close the session (mirrors how StreamingResponse
    finalizes the generator on disconnect)."""
    from openlia_server.services.runtime import RefreshingChatRunner

    factory = _SpyFactory()
    runner = RefreshingChatRunner(factory)

    gen = runner.run(department_id="secretary", user_id="u1", messages=[])
    async for _ in gen:
        break
    await gen.aclose()
    assert factory.opened[0].closed is True
