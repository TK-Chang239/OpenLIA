"""Ensure ``_fakes.py`` (sibling module) is importable from RS tests.

The parent conftest adds test_llm/test_runtime to sys.path; this one
adds the report_dash_rs subdir so ``from _fakes import ...`` resolves.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
