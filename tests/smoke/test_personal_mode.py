"""Personal-mode smoke tests against a running container."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx


def test_healthz_returns_personal(run_container: Callable[..., dict[str, Any]]) -> None:
    info = run_container(env={"OPENLIA_MODE": "personal"})
    resp = httpx.get(f"{info['base_url']}/healthz", timeout=5.0)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("mode") == "personal"


def test_api_prefix_accessible(run_container: Callable[..., dict[str, Any]]) -> None:
    info = run_container(env={"OPENLIA_MODE": "personal"})
    resp = httpx.get(f"{info['base_url']}/api/healthz", timeout=5.0)
    assert resp.status_code == 200


def test_spa_served_from_root(run_container: Callable[..., dict[str, Any]]) -> None:
    info = run_container(env={"OPENLIA_MODE": "personal"})
    resp = httpx.get(f"{info['base_url']}/", timeout=5.0)
    assert resp.status_code == 200
    assert '<div id="root">' in resp.text


def test_setup_wizard_reachable(run_container: Callable[..., dict[str, Any]]) -> None:
    info = run_container(env={"OPENLIA_MODE": "personal"})
    resp = httpx.get(f"{info['base_url']}/api/setup/state", timeout=5.0)
    # 200 (wizard pending) or 403 (already complete) — either proves the route is wired.
    assert resp.status_code in {200, 403}


def test_fresh_volume_migrates(run_container: Callable[..., dict[str, Any]]) -> None:
    """Empty data volume must trigger Alembic upgrade on container start."""
    info = run_container(
        env={"OPENLIA_MODE": "personal"},
        health_timeout_s=30.0,
    )
    resp = httpx.get(f"{info['base_url']}/healthz", timeout=5.0)
    assert resp.status_code == 200
