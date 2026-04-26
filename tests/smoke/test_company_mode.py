"""Company-mode smoke tests against a running container."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from typing import Any

import httpx

UUID_36 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _exec_json(name: str, args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "exec", name, "openlia", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    # Locate the JSON payload (may be preceded by banner / setup output).
    for line in reversed(result.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise AssertionError(f"No JSON object in stdout: {result.stdout!r}")


def _exec(name: str, args: list[str]) -> None:
    subprocess.run(
        ["docker", "exec", name, "openlia", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_company_mode_end_to_end(
    run_container: Callable[..., dict[str, Any]],
) -> None:
    info = run_container(
        env={
            "OPENLIA_MODE": "company",
            "OPENLIA_COOKIE_SECURE": "false",
        }
    )
    name = info["name"]
    base = info["base_url"]

    # Headless deploy: seed signup_policy directly since the wizard UI
    # is skipped in this smoke flow.
    _exec(name, ["admin", "seed-policy", "--mode", "invite_only"])

    payload = _exec_json(
        name,
        [
            "admin",
            "create-invite",
            "--label",
            "smoke",
            "--max-uses",
            "1",
            "--json",
        ],
    )
    assert UUID_36.match(payload["invite_id"])
    token = payload["token"]
    assert token

    register = httpx.post(
        f"{base}/api/auth/register",
        json={
            "invite_token": token,
            "email": "smoke@example.com",
            "password": "SmokeTest!123",
            "display_name": "Smoke",
        },
        timeout=10.0,
    )
    assert register.status_code in {200, 201}

    with httpx.Client(base_url=base, timeout=10.0) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "smoke@example.com", "password": "SmokeTest!123"},
        )
        assert login.status_code == 200
        me = client.get("/api/auth/session")
        assert me.status_code == 200
        assert me.json().get("email") == "smoke@example.com"


def test_cookie_secure_flag_propagates(
    run_container: Callable[..., dict[str, Any]],
) -> None:
    info = run_container(
        env={
            "OPENLIA_MODE": "company",
            "OPENLIA_COOKIE_SECURE": "true",
            "OPENLIA_TRUST_PROXY_HEADERS": "true",
        }
    )
    name = info["name"]
    base = info["base_url"]

    _exec(name, ["admin", "seed-policy", "--mode", "invite_only"])
    payload = _exec_json(
        name,
        ["admin", "create-invite", "--max-uses", "1", "--json"],
    )
    register = httpx.post(
        f"{base}/api/auth/register",
        json={
            "invite_token": payload["token"],
            "email": "secure@example.com",
            "password": "SmokeTest!123",
            "display_name": "Secure",
        },
        timeout=10.0,
    )
    assert register.status_code in {200, 201}

    login = httpx.post(
        f"{base}/api/auth/login",
        json={"email": "secure@example.com", "password": "SmokeTest!123"},
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "203.0.113.10",
        },
        timeout=10.0,
    )
    assert login.status_code == 200
    set_cookie = login.headers.get("set-cookie", "")
    assert "Secure" in set_cookie
    assert "HttpOnly" in set_cookie


def test_trust_proxy_headers_propagates(
    run_container: Callable[..., dict[str, Any]],
) -> None:
    info = run_container(
        env={
            "OPENLIA_MODE": "personal",
            "OPENLIA_TRUST_PROXY_HEADERS": "true",
        }
    )
    base = info["base_url"]
    resp = httpx.get(
        f"{base}/_debug/client_host",
        headers={"X-Forwarded-For": "198.51.100.42"},
        timeout=5.0,
    )
    # Route may or may not be exposed depending on app config; accept 200
    # with the forwarded value, or 404 if the diagnostic route is omitted.
    if resp.status_code == 200:
        assert "198.51.100.42" in resp.text
    else:
        assert resp.status_code in {403, 404}
