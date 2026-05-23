"""Tool abstractions for the v2.3 researcher.

A research tool is a small, focused capability the LLM can invoke
during RESEARCH to fetch one piece of evidence. Each invocation
returns a ``ToolResult`` carrying:

  - ``payload``  — the raw JSON the model sees in the next turn
  - ``provenance`` — a v2.3 ``Provenance`` instance the researcher
    attaches to any ``BundleFact`` derived from this evidence
  - ``summary`` — a one-line human string useful for SSE events and
    for the model when the payload is large

Design choices:

- Tools are sync. The researcher runs inside a thread off the
  FastAPI event loop, just like the other v2.3 stages.
- ``execute`` is a callable rather than an abstract method so test
  fakes can be assembled inline without a subclass.
- Provenance is the v2.3 ``Provenance`` discriminated union — the
  same object that lands on the BundleFact. No translation step.
- The ``ToolDescriptor`` is a thin JSON-Schema-like view used by
  the LLM client to build the provider's tools payload, kept
  separate from execution so it can be inspected without running.

Errors raised inside ``execute`` are caught by the dispatcher and
fed back to the LLM as a structured error payload — the model can
correct itself or try a different tool.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..schemas import Provenance


class ToolExecutionError(RuntimeError):
    """A tool's ``execute`` raised. Captured and surfaced back to the LLM."""


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Successful tool invocation result."""

    payload: dict[str, Any]
    provenance: Provenance
    summary: str = ""


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Provider-agnostic description used to build the LLM's tools array."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the tool's args


@dataclass(slots=True)
class ResearchTool:
    """One callable research capability + its descriptor + executor.

    ``execute`` receives the JSON arguments emitted by the model and
    returns a ``ToolResult``. It MUST raise ``ToolExecutionError`` for
    expected failures (bad ticker, upstream 404). The runtime catches
    every exception, so other raises also surface as structured
    errors but are logged as unexpected.
    """

    descriptor: ToolDescriptor
    execute: Callable[[dict[str, Any]], ToolResult]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.descriptor.name
