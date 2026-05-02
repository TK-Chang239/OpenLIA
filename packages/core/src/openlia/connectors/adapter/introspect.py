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
        # Surface-narrowing: only methods whose `__module__` matches the
        # importing module are returned. Methods inherited from a parent
        # class defined in a different module (e.g. xdk.Client's OAuth
        # helpers when XClient subclasses it) are implementation detail
        # and must not leak into the chat-toolbox surface.
        target_modules = {module_name}
        for fn_name in dir(cls):
            if fn_name.startswith("_"):
                continue
            fn = getattr(cls, fn_name, None)
            if not inspect.isfunction(fn):
                continue
            owner_module = getattr(fn, "__module__", None)
            if owner_module not in target_modules:
                continue
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                continue
            out.append(
                CallableDefinition(
                    qualname=f"{cls_name}.{fn_name}",
                    signature=sig,
                    doc=inspect.getdoc(fn) or "",
                )
            )
        return out

    # No cls_name → walk every public class in the module (wizard adapter path).
    for c_name, cls in inspect.getmembers(mod, inspect.isclass):
        for fn_name, fn in inspect.getmembers(cls, inspect.isfunction):
            if fn_name.startswith("_"):
                continue
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                continue
            out.append(
                CallableDefinition(
                    qualname=f"{c_name}.{fn_name}",
                    signature=sig,
                    doc=inspect.getdoc(fn) or "",
                )
            )
    return out
