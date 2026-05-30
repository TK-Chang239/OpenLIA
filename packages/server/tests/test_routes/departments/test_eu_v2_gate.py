# packages/server/tests/test_routes/departments/test_eu_v2_gate.py

from openlia_server.routes.departments._eu_v2_gate import eu_v2_enabled


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EARNINGS_ENGINE_VERSION", raising=False)
    assert eu_v2_enabled() is False


def test_enabled_when_v2(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    assert eu_v2_enabled() is True


def test_case_insensitive(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "V2")
    assert eu_v2_enabled() is True
