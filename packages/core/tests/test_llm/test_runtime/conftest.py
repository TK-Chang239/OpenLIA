"""Ensure `_fakes.py` (sibling module with shared helper classes) is importable.

Pytest runs with --import-mode=importlib and no package __init__.py files,
so sibling test files cannot import each other by package path. This
conftest puts the current directory on sys.path so `from _fakes import X`
works inside every test module in this folder.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
