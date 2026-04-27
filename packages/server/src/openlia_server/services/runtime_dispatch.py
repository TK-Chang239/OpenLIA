"""Server-side re-export of the core runtime dispatch helper.

The implementation moved to `openlia.llm.runtime.runtime_dispatch` during
H3.3b so ChatRunner / ReportRunner (which live in core) can import it
without violating the layer rule (`openlia.*` cannot import
`openlia_server.*`). This module is kept as a thin shim to avoid breaking
existing server-side imports.
"""

from __future__ import annotations

from openlia.llm.runtime.runtime_dispatch import (
    ToolCallRequest,
    ToolCallResult,
    _normalize_payload,
    _short_args,
    _summary_for,
    dispatch_many,
    dispatch_with_envelope,
    tools_for_run,
)

__all__ = [
    "ToolCallRequest",
    "ToolCallResult",
    "_normalize_payload",
    "_short_args",
    "_summary_for",
    "dispatch_many",
    "dispatch_with_envelope",
    "tools_for_run",
]
