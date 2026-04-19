"""Expose this test directory on sys.path so sibling test modules can
`from _fakes import ...` without relying on a tests.* package (which
does not exist under --import-mode=importlib)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
