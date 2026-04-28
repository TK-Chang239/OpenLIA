"""Wizard-time adapter LLM subsystem.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.

The adapter resolves a department-declared `RunnerNeed` against a connector's
discovered tools (MCP) or callables (python_lib introspection), producing a
draft `CallableSpec` row that the wizard surfaces for admin approval.
"""

from __future__ import annotations

from openlia.connectors.adapter.introspect import introspect_python_lib

__all__ = [
    "introspect_python_lib",
]
