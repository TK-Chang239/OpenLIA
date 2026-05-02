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


def introspect_python_lib(
    module_name: str, *, cls_name: str | None = None
) -> list[CallableDefinition]:
    """Return public class methods declared on `module_name`.

    When `cls_name` is provided, only methods of that class (including
    inherited from non-`object` ancestors) are returned. Without it,
    every public class in the module is walked — useful for the wizard
    adapter LLM, but unsafe for chat-toolbox surface in wrapper modules
    that re-import a parent SDK class.

    Each entry is a `CallableDefinition(qualname=f"{Class}.{method}", signature=..., doc=...)`.
    """
    mod = importlib.import_module(module_name)
    out: list[CallableDefinition] = []

    if cls_name is not None:
        cls = getattr(mod, cls_name, None)
        if not inspect.isclass(cls):
            return out
        classes: list[tuple[str, type]] = [(cls_name, cls)]
    else:
        classes = list(inspect.getmembers(mod, inspect.isclass))

    for c_name, cls in classes:
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
                    qualname=f"{c_name}.{fn_name}",
                    signature=sig,
                    doc=doc,
                )
            )
    return out
