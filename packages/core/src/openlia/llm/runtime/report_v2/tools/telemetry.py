"""Typed tool-use round telemetry (PR 8b).

Each tool-use round emits a `ToolRoundEvent` tagged with `round_type`
(inspect / call / error). Three diagnostic pathologies map to round-type
distributions:

* 6 x inspect, 0 x call -> routing problem; the `use_when` hints aren't
  disambiguating (fix at the manifest layer).
* 6 x call, all `result_null=True` -> data problem; the helper found
  nothing in the facts pack (fix in the extractor or data source).
* inspect -> call -> inspect -> call alternating -> interface confusion;
  the model is reading the doc, calling, getting an error or unexpected
  result, re-reading (fix in either the schema, the doc clarity, or the
  helper's error shape).

The dispatcher emits these events; per-section terminal-state metadata
aggregates them by type so the operator can tell pathologies apart from
the surfaced report metadata without re-running.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

RoundType = Literal["inspect", "call", "error"]
DispatchTier = Literal["body", "synthesis", "meta"]


class ToolRoundEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str
    attempt: int
    round_index: int
    round_type: RoundType
    tool_name: str
    args_validated: bool = True
    result_null: bool = False
    elapsed_ms: int = 0
    dispatch_tier: DispatchTier = "body"
