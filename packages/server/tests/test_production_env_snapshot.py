"""Pin the production-env contract.

The deploy recipes under ``deploy/*/docker-compose.yml`` rely on a fixed
set of OPENLIA_* env keys. ``fixtures/production_env.yaml`` is the
canonical snapshot; this test asserts that every required key is still
present so accidental drops in the YAML show up as a test failure.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REQUIRED_KEYS = {
    "OPENLIA_MODE",
    "OPENLIA_DB_URL",
    "OPENLIA_FRONTEND_DIST",
    "OPENLIA_TRUST_PROXY_HEADERS",
    "OPENLIA_COOKIE_SECURE",
    "OPENLIA_SCHEDULER_ENABLED",
}


def test_production_env_snapshot_has_required_keys() -> None:
    fixture = Path(__file__).parent / "fixtures" / "production_env.yaml"
    data = yaml.safe_load(fixture.read_text())
    assert isinstance(data, dict)
    missing = REQUIRED_KEYS - data.keys()
    assert not missing, f"production_env.yaml missing keys: {sorted(missing)}"
