# packages/server/tests/test_routes/departments/test_eu_v2_gate.py

from openlia_server.routes.departments._eu_v2_gate import eu_v2_enabled


def test_enabled_when_flag_unset(monkeypatch):
    # v2 is the sole live Earnings Update engine; the gate is retired and
    # any value (including unset) keeps it on. Captures the production 503
    # regression where deploy configs never set EARNINGS_ENGINE_VERSION.
    monkeypatch.delenv("EARNINGS_ENGINE_VERSION", raising=False)
    assert eu_v2_enabled() is True


def test_enabled_when_v2(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    assert eu_v2_enabled() is True


def test_enabled_for_any_value(monkeypatch):
    monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "anything")
    assert eu_v2_enabled() is True
