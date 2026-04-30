"""`.env` loading: regression test for the legacy/v2 DB-path footgun.

The default `OPENLIA_DB_URL` (~/.openlia/openlia.db) is pinned to an old
alembic head from the abandoned cutover branch on this dev machine. The
v2 branch needs `~/.openlia/openlia-v2.db`. Without dotenv loading, every
fresh shell missed the override and the server crashed with
"Can't locate revision identified by '20260427_1900_drop_dp'".

This test pins down the contract: importing `openlia_server.cli` while a
`.env` file in the working directory sets `OPENLIA_DB_URL` must surface
that value in `os.environ`. Process env is preserved (override=False).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap


def test_cli_loads_env_file_in_cwd(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENLIA_DB_URL=sqlite:///from-dotenv.db\n")

    # Run a fresh interpreter so the `cli` module's import-time `load_dotenv`
    # runs in `tmp_path` (its CWD) and we can assert on the loaded value
    # without polluting the test process env.
    script = textwrap.dedent(
        """
        import os
        os.environ.pop("OPENLIA_DB_URL", None)
        import openlia_server.cli  # noqa: F401  -- import for side effect
        print(os.environ.get("OPENLIA_DB_URL", ""))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "sqlite:///from-dotenv.db", result.stderr


def test_existing_env_var_takes_precedence_over_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENLIA_DB_URL=sqlite:///from-dotenv.db\n")

    script = textwrap.dedent(
        """
        import os
        import openlia_server.cli  # noqa: F401
        print(os.environ.get("OPENLIA_DB_URL", ""))
        """
    )
    env = {**os.environ, "OPENLIA_DB_URL": "sqlite:///from-process-env.db"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert result.stdout.strip() == "sqlite:///from-process-env.db", result.stderr


def test_env_local_overlays_env(tmp_path) -> None:
    (tmp_path / ".env").write_text("OPENLIA_DB_URL=sqlite:///from-env.db\n")
    (tmp_path / ".env.local").write_text("OPENLIA_DB_URL=sqlite:///from-env-local.db\n")

    script = textwrap.dedent(
        """
        import os
        os.environ.pop("OPENLIA_DB_URL", None)
        import openlia_server.cli  # noqa: F401
        print(os.environ.get("OPENLIA_DB_URL", ""))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    # `.env.local` is loaded with override=False AFTER `.env` populated the
    # value, so the first writer wins. We document this rather than fight
    # python-dotenv's semantics: `.env` sets, `.env.local` only fills gaps.
    # If we ever want true overlay, switch the second call to override=True.
    assert result.stdout.strip() == "sqlite:///from-env.db", result.stderr
