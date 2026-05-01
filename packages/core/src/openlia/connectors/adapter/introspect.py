"""Python-lib introspection for the wizard-time adapter LLM.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.

Walks a python_lib connector's public classes and surfaces the methods the
adapter LLM may bind a `RunnerNeed` to. Private members (leading `_`) and
members whose `inspect.signature(...)` raises are filtered out.
"""

from __future__ import annotations

import importlib
import inspect

from openlia.connectors.types import CallableDefinition


def introspect_python_lib(module_name: str) -> list[CallableDefinition]:
    """Return public class methods declared on `module_name`.

    Each entry is a `CallableDefinition(qualname=f"{Class}.{method}", signature=..., doc=...)`.
    """

    mod = importlib.import_module(module_name)
    out: list[CallableDefinition] = []
    for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
        for fn_name, fn in inspect.getmembers(cls, inspect.isfunction):
            if fn_name.startswith("_"):
                continue
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                continue
            doc = inspect.getdoc(fn) or ""
            out.append(
                CallableDefinition(
                    qualname=f"{cls_name}.{fn_name}",
                    signature=sig,
                    doc=doc,
                )
            )
    return out
