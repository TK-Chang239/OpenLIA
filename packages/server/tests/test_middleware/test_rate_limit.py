"""Tests for middleware.rate_limit — sliding-window counters."""
from __future__ import annotations

import time

import pytest

from openlia_server.middleware.rate_limit import SlidingWindowLimiter


class TestSlidingWindow:
    def test_allows_under_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            assert lim.check_and_tick("key", limit=5, window_seconds=60) is True

    def test_blocks_over_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.check_and_tick("k", limit=5, window_seconds=60)
        assert lim.check_and_tick("k", limit=5, window_seconds=60) is False

    def test_window_resets_after_expiry(self, monkeypatch):
        lim = SlidingWindowLimiter()
        base = [1000.0]
        monkeypatch.setattr("openlia_server.middleware.rate_limit.time.monotonic", lambda: base[0])

        for _ in range(5):
            lim.check_and_tick("k", limit=5, window_seconds=60)
        base[0] += 61
        assert lim.check_and_tick("k", limit=5, window_seconds=60) is True

    def test_separate_keys_isolated(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.check_and_tick("a", limit=5, window_seconds=60)
        assert lim.check_and_tick("a", limit=5, window_seconds=60) is False
        assert lim.check_and_tick("b", limit=5, window_seconds=60) is True
