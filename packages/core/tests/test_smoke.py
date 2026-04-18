"""Smoke tests proving the openlia-core package is installable and importable."""

import subprocess
import sys

import openlia
from openlia.exceptions import OpenLIAError


def test_package_has_version():
    assert hasattr(openlia, "__version__")
    assert isinstance(openlia.__version__, str)
    assert openlia.__version__  # non-empty


def test_base_exception_is_subclass_of_exception():
    assert issubclass(OpenLIAError, Exception)


def test_no_web_imports_in_core():
    """openlia-core must not import any web framework. The boundary rule from CLAUDE.md.

    Runs in a subprocess so the server-tests' fastapi import doesn't contaminate
    sys.modules in the parent pytest session.
    """
    probe = (
        "import openlia, sys; "
        "forbidden = {'fastapi', 'uvicorn', 'starlette'}; "
        "leaked = sorted(forbidden & set(sys.modules.keys())); "
        "assert not leaked, f'core leaked web imports: {leaked}'"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
