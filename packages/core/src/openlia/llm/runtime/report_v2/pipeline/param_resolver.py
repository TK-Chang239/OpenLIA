"""Param resolver — explicit → derived → default → unresolved priority chain.

See docs/superpowers/plans/2026-05-21-equity-research-v2.2.md §P5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.tools.library_helpers import get_helper


@dataclass
class ResolverResult:
    resolved: dict[str, Any]
    provenance: dict[str, str]
    failed: bool = False
    unresolved: list[str] = field(default_factory=list)
    reason: str | None = None


def resolve_params(
    helper_name: str,
    explicit: dict[str, Any],
    research_pool: Any,
    llm: Any,
) -> ResolverResult:
    """Resolve parameters for a helper using explicit → derived → default → unresolved."""
    helper = get_helper(helper_name)
    params = helper.schema.params

    resolved: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    unresolved: list[str] = []

    for name, param in params.items():
        # 1. Explicit
        if name in explicit:
            resolved[name] = explicit[name]
            provenance[name] = "explicit"
            continue

        # 2. Derivation via LLM
        if param.derivation is not None:
            try:
                response = llm.call(
                    system=(
                        "You are a derivation resolver. Return JSON with a single key"
                        " 'value' containing the derived value, or null if it cannot"
                        " be derived."
                    ),
                    user={"rule": param.derivation, "research_pool": research_pool},
                )
                derived_value = response.get("value") if isinstance(response, dict) else None
            except Exception:
                derived_value = None

            if derived_value is not None:
                resolved[name] = derived_value
                provenance[name] = "derived"
                continue

        # 3. Default
        if param.default is not None:
            resolved[name] = param.default
            provenance[name] = "default"
            continue

        # 4. Unresolved
        if param.required:
            unresolved.append(name)

    failed = len(unresolved) > 0
    reason: str | None = None
    if failed:
        reason = f"required params could not be resolved: {', '.join(unresolved)}"

    return ResolverResult(
        resolved=resolved,
        provenance=provenance,
        failed=failed,
        unresolved=unresolved,
        reason=reason,
    )
