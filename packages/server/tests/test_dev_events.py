"""Coverage for the dev-mode event bus."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from openlia_server import dev_events


@pytest.fixture(autouse=True)
def _reset(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENLIA_DEV_EVENTS_LOG", str(tmp_path / "dev.jsonl"))
    dev_events.reset_for_tests()
    yield
    dev_events.reset_for_tests()


def test_record_is_noop_when_dev_mode_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENLIA_DEV_MODE", raising=False)
    dev_events.record("chat.request", "hello")
    assert dev_events.snapshot() == []
    log = Path(tmp_path / "dev.jsonl")
    assert not log.exists()


def test_record_appends_to_ring_and_jsonl_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_DEV_MODE", "1")
    dev_events.record("chat.request", "hi", payload={"user": "u-1"})
    snap = dev_events.snapshot()
    assert len(snap) == 1
    assert snap[0]["category"] == "chat.request"
    assert snap[0]["message"] == "hi"
    assert snap[0]["payload"] == {"user": "u-1"}
    assert snap[0]["seq"] == 1
    log = Path(tmp_path / "dev.jsonl")
    assert log.exists()
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows == snap


def test_ring_is_capped(monkeypatch):
    monkeypatch.setenv("OPENLIA_DEV_MODE", "1")
    for i in range(dev_events._RING_MAX + 50):
        dev_events.record("x", str(i))
    snap = dev_events.snapshot()
    assert len(snap) == dev_events._RING_MAX
    # Oldest were evicted; newest preserved.
    assert snap[-1]["message"] == str(dev_events._RING_MAX + 50 - 1)


@pytest.mark.asyncio
async def test_stream_replays_then_yields_live_events(monkeypatch):
    monkeypatch.setenv("OPENLIA_DEV_MODE", "1")
    dev_events.record("chat.request", "first")
    dev_events.record("chat.event", "second")

    iterator = dev_events.stream().__aiter__()

    # First two yields are the replay snapshot.
    a = await asyncio.wait_for(iterator.__anext__(), timeout=0.5)
    b = await asyncio.wait_for(iterator.__anext__(), timeout=0.5)
    assert a["message"] == "first"
    assert b["message"] == "second"

    # A live event after subscription should arrive next.
    dev_events.record("chat.event", "third")
    c = await asyncio.wait_for(iterator.__anext__(), timeout=0.5)
    assert c["message"] == "third"
