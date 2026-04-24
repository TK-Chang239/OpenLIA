"""Expose test dir on sys.path so sibling test modules can
`from _macro_research_fakes import ...`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
