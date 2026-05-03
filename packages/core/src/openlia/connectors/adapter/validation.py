"""Resolver validation gate (Phase 6).

Validates a `CallableSpec` produced by the manual-pick resolver against
the need's contract. Run on save, before persisting and before smoke.

Checks:
  1. Every `param_binding.transform` (when not None) is in
     `ALLOWED_TRANSFORMS`.
  2. `field_map` rules:
     - forbidden on non-`list[dict]` shapes.
     - on `list[dict]` shapes, may be `None` (none declared) or a dict.
     - when the dict is non-empty, its keys MUST cover the need's
       `canonical_keys` set.
     - the empty dict `{}` is the explicit "endpoint already returns
       canonical-keyed items" sentinel.
"""

from __future__ import annotations

from openlia.connectors.types import (
    ALLOWED_TRANSFORMS,
    CallableSpec,
    RunnerNeed,
)


class ValidationError(ValueError):
    """Raised when a resolved CallableSpec fails the validation gate."""


def validate_resolved_spec(*, spec: CallableSpec, need: RunnerNeed) -> None:
    """Raise `ValidationError` if `spec` is malformed for `need`."""
    for caller_name, binding in spec.param_bindings.items():
        if binding.transform is None:
            continue
        if binding.transform not in ALLOWED_TRANSFORMS:
            raise ValidationError(
                f"transform {binding.transform!r} (on param_binding "
                f"{caller_name!r}) is not in ALLOWED_TRANSFORMS"
            )

    if spec.shape != "list[dict]":
        if spec.field_map is not None:
            raise ValidationError(
                f"field_map is only valid for shape 'list[dict]'; spec shape is {spec.shape!r}"
            )
        return

    fm = spec.field_map
    if fm is None:
        # list[dict] with no declared field_map. Allowed only when the
        # need has no canonical_keys (which the loader prevents). If we
        # get here with canonical_keys present, that's a contract miss.
        if need.canonical_keys:
            raise ValidationError(
                f"need {need.id!r} declares canonical_keys but spec has "
                f"no field_map; either populate the rename map or set "
                f"field_map={{}} (endpoint already canonical)."
            )
        return

    if fm == {}:
        return

    canonical = set(need.canonical_keys.keys()) if need.canonical_keys else set()
    missing = canonical - set(fm.keys())
    if missing:
        raise ValidationError(
            f"field_map is missing canonical keys for need {need.id!r}: {missing}"
        )


__all__ = ["ValidationError", "validate_resolved_spec"]
