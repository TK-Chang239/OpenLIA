"""`python_lib` transport — in-process import + method dispatch.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §4.2,
§6.4. No sandboxing per locked-down §13.2.

The transport lazily imports the configured module, instantiates the class
described by `InstanceFactory` (substituting `$ENV_VAR_NAME` placeholders
in `args` from the secrets dict supplied at construction), and routes
`call_tool(name, **arguments)` to the corresponding bound method on the
cached instance.
"""

from __future__ import annotations

import importlib
import inspect
from inspect import getdoc
from typing import Any

from openlia.connectors.types import InstanceFactory


class PythonLibTransport:
    """Implements `CallableTransport` for python_lib connectors."""

    def __init__(
        self,
        *,
        module: str,
        instance_factory: InstanceFactory,
        secrets: dict[str, str],
    ) -> None:
        self._module_name = module
        self._instance_factory = instance_factory
        self._secrets = secrets
        self._instance: Any | None = None

    def _resolve_instance(self) -> Any:
        if self._instance is not None:
            return self._instance
        mod = importlib.import_module(self._module_name)
        cls = getattr(mod, self._instance_factory.cls)
        resolved_args = {
            k: (self._secrets[v[1:]] if isinstance(v, str) and v.startswith("$") else v)
            for k, v in self._instance_factory.args.items()
        }
        self._instance = cls(**resolved_args)
        return self._instance

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        inst = self._resolve_instance()
        method = getattr(inst, name)
        result = method(**arguments)
        if inspect.isawaitable(result):
            result = await result
        return result

    async def list_tools(self) -> list[dict]:
        """Return MCP-shaped descriptors for every public method on the instance.

        Phase 6 ships a richer `introspect_python_lib` walker that extracts
        argument schemas from typed signatures; Phase 5 only needs to surface
        callable names + docs so the dispatcher can route invocations.
        """
        inst = self._resolve_instance()
        out: list[dict] = []
        for name, member in inspect.getmembers(inst, predicate=inspect.ismethod):
            if name.startswith("_"):
                continue
            out.append(
                {
                    "name": name,
                    "description": getdoc(member) or "",
                    "input_schema": {},
                }
            )
        return out

    async def aclose(self) -> None:
        self._instance = None
