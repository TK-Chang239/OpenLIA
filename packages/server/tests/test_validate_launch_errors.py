"""Unit tests for `_validate_launch` error enrichment.

When a python_lib import fails, the user-facing `last_error` should include
enough diagnostic context to be actionable from the wizard UI: the module
name, the Python interpreter path (so the user knows which venv to install
into), the pip name/version, and the underlying exception.
"""

from __future__ import annotations

import sys

import pytest
from openlia_server.services import connectors_service


@pytest.mark.asyncio
async def test_python_lib_import_failure_includes_actionable_context() -> None:
    launch = {
        "modes": [
            {
                "kind": "python_lib",
                "pip_name": "eodhd",
                "pip_version": "",
                "import_module": "definitely_not_a_real_module_xyz",
                "instance_factory": {"cls": "APIClient", "args": {}},
            }
        ]
    }
    result = await connectors_service._validate_launch(launch, secrets={})
    assert isinstance(result, connectors_service.ValidationFailure)
    err = result.error

    # Original error preserved
    assert "definitely_not_a_real_module_xyz" in err
    # User can see which interpreter we tried
    assert sys.executable in err
    # User can see the pip package name to install
    assert "eodhd" in err
    # Hint about how to fix
    assert "pip install" in err.lower()
    # Multi-line so the UI's "Show details" toggle activates
    assert "\n" in err


@pytest.mark.asyncio
async def test_remote_mcp_failure_does_not_get_python_lib_hints() -> None:
    """Remote MCP failures should NOT get python-specific install hints."""
    launch = {
        "modes": [
            {
                "kind": "remote_mcp",
                "url": "http://127.0.0.1:1/never-listens",
                "headers": {},
            }
        ]
    }
    result = await connectors_service._validate_launch(launch, secrets={})
    assert isinstance(result, connectors_service.ValidationFailure)
    err = result.error
    assert "pip install" not in err.lower()
    assert sys.executable not in err
