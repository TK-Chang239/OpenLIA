"""Meta-tools: `get_helper_docs` for the inspect layer.

When a complex helper has a `doc_path`, the LLM can fetch its full doc
(signature, parameter conventions, worked example) via `get_helper_docs(name)`
before invoking the helper itself. The function is cached per-run because
doc paths don't change mid-report.
"""

from __future__ import annotations

import functools
from pathlib import Path

from openlia.llm.runtime.report_v2.tools.registry import ToolRegistry


def make_get_helper_docs(registry: ToolRegistry):
    """Build a `get_helper_docs(name) -> str` function backed by the registry.

    Returns the markdown content at the handler's `doc_path`. Raises
    `KeyError` when the handler doesn't exist; `FileNotFoundError` when the
    handler has no doc_path or the file is missing.
    """

    @functools.lru_cache(maxsize=128)
    def get_helper_docs(name: str) -> str:
        handler = registry.get(name)
        if not handler.doc_path:
            raise FileNotFoundError(
                f"helper {name!r} is classified `simple`; signature is inline in the manifest"
            )
        path = Path(handler.doc_path)
        if not path.exists():
            raise FileNotFoundError(f"doc_path for helper {name!r} not found: {path}")
        return path.read_text(encoding="utf-8")

    return get_helper_docs
