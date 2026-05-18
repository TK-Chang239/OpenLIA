from __future__ import annotations

import pytest


def test_env_var_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

    monkeypatch.setenv("OPENLIA_REPORT_RENDER_BASE_URL", "https://example.test")
    resolver = RenderBaseUrlResolver(
        server_url="http://127.0.0.1:8000",
        is_spa_served_locally=lambda: False,
        probe=lambda url: False,
    )
    assert resolver.resolve() == "https://example.test"


def test_falls_through_to_local_spa(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    resolver = RenderBaseUrlResolver(
        server_url="http://127.0.0.1:8000",
        is_spa_served_locally=lambda: True,
        probe=lambda url: False,
    )
    assert resolver.resolve() == "http://127.0.0.1:8000"


def test_falls_through_to_vite_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    probes: list[str] = []

    def fake_probe(url: str) -> bool:
        probes.append(url)
        return True

    resolver = RenderBaseUrlResolver(
        server_url="http://127.0.0.1:8000",
        is_spa_served_locally=lambda: False,
        probe=fake_probe,
    )
    # Default probes :8080 first (this project's Vite port); first hit wins.
    assert resolver.resolve() == "http://127.0.0.1:8080"
    assert probes == ["http://127.0.0.1:8080"]


def test_probes_fallback_vite_port_when_first_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    probes: list[str] = []

    def fake_probe(url: str) -> bool:
        probes.append(url)
        return url.endswith(":5173")

    resolver = RenderBaseUrlResolver(
        server_url="http://127.0.0.1:8000",
        is_spa_served_locally=lambda: False,
        probe=fake_probe,
    )
    # When :8080 is closed but :5173 answers, the resolver should pick :5173.
    assert resolver.resolve() == "http://127.0.0.1:5173"
    assert probes == ["http://127.0.0.1:8080", "http://127.0.0.1:5173"]


def test_returns_none_when_no_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    resolver = RenderBaseUrlResolver(
        server_url="http://127.0.0.1:8000",
        is_spa_served_locally=lambda: False,
        probe=lambda url: False,
    )
    assert resolver.resolve() is None


def test_invalidate_re_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.services.render_base_url import RenderBaseUrlResolver

    monkeypatch.delenv("OPENLIA_REPORT_RENDER_BASE_URL", raising=False)
    # First resolve round: nothing answers. After invalidate, :8080 answers.
    rounds = {"n": 0}

    def fake_probe(url: str) -> bool:
        if rounds["n"] == 0:
            return False
        return url.endswith(":8080")

    resolver = RenderBaseUrlResolver(
        server_url="http://127.0.0.1:8000",
        is_spa_served_locally=lambda: False,
        probe=fake_probe,
    )
    assert resolver.resolve() is None
    rounds["n"] = 1
    resolver.invalidate()
    assert resolver.resolve() == "http://127.0.0.1:8080"


def test_default_probe_returns_false_for_closed_port() -> None:
    from openlia_server.services.render_base_url import default_probe

    assert default_probe("http://127.0.0.1:1", timeout_sec=0.05) is False
