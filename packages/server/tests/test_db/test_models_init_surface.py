"""Package-surface invariants for `openlia_server.db.models`.

`models/__init__.py` is Plan 1a surface only. The `register_all` shim is the
one-stop side-effect import that registers every shipped ORM module. Tests
here lock both contracts so later plans cannot quietly re-export themselves
through the Plan 1a namespace.
"""

from __future__ import annotations

import subprocess
import sys


def test_models_init_exports_only_plan_1a_submodules() -> None:
    from openlia_server.db import models as models_pkg

    assert set(models_pkg.__all__) == {"auth", "config", "content", "infrastructure"}


def test_models_init_does_not_import_plan_1b_or_later_in_subprocess() -> None:
    """Fresh interpreter check: importing only `openlia_server.db.models`
    (without the register_all shim) must not pull Plan 1B+ modules."""
    script = (
        "import sys; "
        "import openlia_server.db.models; "
        "loaded = sorted(k for k in sys.modules if k.startswith('openlia_server.db.models')); "
        "print('\\n'.join(loaded))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = set(proc.stdout.strip().splitlines())
    forbidden = {
        "openlia_server.db.models.dashboard",
        "openlia_server.db.models.scheduler",
        "openlia_server.db.models.departments",
    }
    leaked = forbidden & loaded
    assert leaked == set(), f"Plan 1b+ submodules leaked through __init__: {leaked}"


def test_register_all_loads_every_shipped_module() -> None:
    """Shim must make every shipped table visible on Base.metadata."""
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.db.base import Base

    tables = set(Base.metadata.tables.keys())
    for t in ("users", "llm_providers", "reports", "wizard_state", "pt_presets", "mb_schedules"):
        assert t in tables, f"{t} missing after register_all import"
