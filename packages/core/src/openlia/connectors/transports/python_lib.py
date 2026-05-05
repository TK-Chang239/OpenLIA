"""`python_lib` transport — in-process import + method dispatch.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §4.2,
§6.4. No sandboxing per locked-down §13.2.

The transport lazily imports the configured module, instantiates the class
described by `InstanceFactory` (substituting `$ENV_VAR_NAME` or `${ENV_VAR_NAME}`
placeholders in `args` from the secrets dict supplied at construction), and
routes `call_tool(name, **arguments)` to the corresponding bound method on
the cached instance.
"""

from __future__ import annotations

import importlib
import inspect
from inspect import getdoc
from typing import Any

from openlia.connectors.types import InstanceFactory

_PRIMITIVE_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _annotation_to_schema_type(annotation: Any) -> str | None:
    """Map a Python annotation to a JSON-schema primitive type.

    Returns None when the annotation is missing, complex (Union without
    a primitive base, generics), or otherwise not a clean fit. Caller
    omits the `type` key in that case.
    """
    if annotation is inspect.Parameter.empty:
        return None
    # `int | None` / Optional[int] → unwrap to the non-None primitive.
    args = getattr(annotation, "__args__", None)
    if args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            annotation = non_none[0]
    return _PRIMITIVE_TYPE_MAP.get(annotation)


def _signature_to_input_schema(method: Any) -> dict[str, Any]:
    """Build a JSON schema for `method`'s call signature.

    Returns `{}` when introspection fails. Otherwise returns a
    `{"type": "object", "properties": {...}, "required": [...]}` shape
    so the function-calling provider can enforce required args.
    """
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        return {}
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name == "self" or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        prop: dict[str, Any] = {}
        schema_type = _annotation_to_schema_type(param.annotation)
        if schema_type is not None:
            prop["type"] = schema_type
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _filter_known_kwargs(method: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return `arguments` filtered to the kwargs `method` accepts.

    If the method's signature includes `**kwargs` (VAR_KEYWORD), pass
    everything through. Otherwise drop any keys not in the signature.
    Falls back to passing everything through when introspection fails
    (e.g. C-extension methods).
    """
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        return arguments
    accepts_varkw = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    if accepts_varkw:
        return arguments
    known = {
        name
        for name, p in sig.parameters.items()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    return {k: v for k, v in arguments.items() if k in known}


def _resolve_placeholder(value: Any, secrets: dict[str, str]) -> Any:
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    name = value[1:]
    if name.startswith("{") and name.endswith("}"):
        name = name[1:-1]
    return secrets[name]


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
            k: _resolve_placeholder(v, self._secrets)
            for k, v in self._instance_factory.args.items()
        }
        self._instance = cls(**resolved_args)
        return self._instance

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        inst = self._resolve_instance()
        # The adapter LLM is shown method qualnames like "APIClient.get_macro"
        # (because that's how `introspect_python_lib` lists them) but the
        # transport binds against the instance, where only the bare method
        # name is an attribute. Strip the class prefix so either form works.
        attr = name.rsplit(".", 1)[-1]
        method = getattr(inst, attr)
        # Filter unknown kwargs unless the method accepts **kwargs. LLMs
        # sometimes synthesize argument names from a tool description that
        # doesn't match the underlying SDK signature (e.g. EODHD's
        # `financial_news` describes `from`/`to` but the Python SDK uses
        # `from_date`/`to_date`). Without filtering, the call raises
        # TypeError and surfaces as a chat-killing 400; the model has no
        # path to recover. Better: drop the bad kwarg, call with what's
        # left, and let any genuine "missing required arg" error bubble
        # up from the SDK with a message the model can act on.
        bound = _filter_known_kwargs(method, arguments)
        result = method(**bound)
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
                    "input_schema": _signature_to_input_schema(member),
                }
            )
        return out

    async def aclose(self) -> None:
        self._instance = None
