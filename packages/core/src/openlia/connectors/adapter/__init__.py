"""Wizard-time adapter LLM subsystem.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.

The adapter resolves a department-declared `RunnerNeed` against a connector's
discovered tools (MCP) or callables (python_lib introspection), producing a
draft `CallableSpec` row that the wizard surfaces for admin approval.
"""

from __future__ import annotations

from openlia.connectors.adapter.callable_spec_resolver import (
    LlmClient,
    ResolverError,
    UnsatisfiableNeed,
    resolve_callable_spec,
)
from openlia.connectors.adapter.canary import CanaryResult, run_canary
from openlia.connectors.adapter.introspect import introspect_python_lib
from openlia.connectors.adapter.manual_pick_resolver import (
    ResolverResult,
    resolve_user_picked_spec,
)
from openlia.connectors.adapter.validation import (
    ValidationError,
    validate_resolved_spec,
)

__all__ = [
    "CanaryResult",
    "LlmClient",
    "ResolverError",
    "ResolverResult",
    "UnsatisfiableNeed",
    "ValidationError",
    "introspect_python_lib",
    "resolve_callable_spec",
    "resolve_user_picked_spec",
    "run_canary",
    "validate_resolved_spec",
]
