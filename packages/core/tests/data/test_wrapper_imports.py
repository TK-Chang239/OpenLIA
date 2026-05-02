"""Verifies that every wrapper module declared by a built-in template
can be imported in the current Python environment.

Each wrapper carries a hard dependency on a third-party PyPI package
(firecrawl-py, eventregistry, xdk). If those aren't declared as
required deps somewhere in the workspace, `_validate_launch` for
the corresponding template fails at install with ModuleNotFoundError
and the user has no clean recovery path.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "openlia.data.eodhd_extended",
        "openlia.data.eventregistry_wrapper",
        "openlia.data.x_wrapper",
    ],
)
def test_builtin_wrapper_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)
