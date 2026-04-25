"""Container-runtime smoke harness.

These tests boot a real Docker container built from the repo's Dockerfile
and exercise the running HTTP surface. They are gated behind the SMOKE
env var so the default `uv run pytest` invocation in CI / dev does not
require Docker.

To run:
    docker build -t openlia:dev .
    SMOKE=1 OPENLIA_IMAGE=openlia:dev uv run pytest tests/smoke/ -v
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every smoke test unless SMOKE=1 is set.

    Only items inside ``tests/smoke/`` are gated — pytest passes the entire
    collected item list to every conftest hook, so we filter on path here.
    """
    if os.environ.get("SMOKE") == "1":
        return
    smoke_dir = str(Path(__file__).parent.resolve())
    skip = pytest.mark.skip(reason="Set SMOKE=1 to run container smoke tests.")
    for item in items:
        if str(Path(item.fspath).resolve()).startswith(smoke_dir):
            item.add_marker(skip)


def _free_port() -> int:
    """Allocate a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(
    check: Callable[[], bool],
    *,
    timeout_s: float = 60.0,
    interval_s: float = 1.0,
    description: str = "condition",
) -> None:
    """Poll ``check`` until it returns truthy or ``timeout_s`` elapses."""
    deadline = time.monotonic() + timeout_s
    last_exc: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(interval_s)
    raise TimeoutError(
        f"Timed out after {timeout_s:.0f}s waiting for {description} (last exception: {last_exc!r})"
    )


@pytest.fixture
def image_tag() -> str:
    return os.environ.get("OPENLIA_IMAGE", "openlia:dev")


@pytest.fixture
def run_container(
    image_tag: str,
) -> Iterator[Callable[..., dict[str, Any]]]:
    """Factory fixture that runs ``docker run`` and tears down on exit.

    Returns a callable ``run_container(env=..., extra_args=...)`` that
    starts a container, waits for ``/healthz`` to respond 200, and yields
    a dict ``{"name", "port", "base_url"}``. Every container started this
    way is removed at fixture teardown.
    """
    started: list[str] = []

    def _start(
        *,
        env: dict[str, str] | None = None,
        extra_args: list[str] | None = None,
        wait_health: bool = True,
        health_timeout_s: float = 60.0,
    ) -> dict[str, Any]:
        port = _free_port()
        name = f"openlia-smoke-{port}"
        cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"{port}:8000",
        ]
        for key, value in (env or {}).items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend(extra_args or [])
        cmd.append(image_tag)
        subprocess.run(cmd, check=True, capture_output=True)
        started.append(name)
        base_url = f"http://127.0.0.1:{port}"
        if wait_health:
            _wait_for(
                lambda: httpx.get(f"{base_url}/healthz", timeout=2.0).status_code == 200,
                timeout_s=health_timeout_s,
                description=f"/healthz on {name}",
            )
        return {"name": name, "port": port, "base_url": base_url}

    try:
        yield _start
    finally:
        for name in started:
            subprocess.run(
                ["docker", "rm", "-f", name],
                check=False,
                capture_output=True,
            )
