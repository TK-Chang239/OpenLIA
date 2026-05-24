"""Pure derivation primitives for writer-time arithmetic.

Writers must never type a calculated number. When a section needs a
derived value (YoY growth, margin, ratio), the writer emits a
``{{DERIVE:method|input_ids|new_id}}`` marker and the WriteStage mint
step calls into one of the functions here. Each returns a ``BundleFact``
carrying a ``ComputedSource`` with ``derived_from`` pointing at the
inputs — so the bundle validator's existing chain walk treats it
identically to any COMPUTE-time fact.

Add new methods here, not in stages or clients. The set is deliberately
small — these cover what writers actually claim in prose. Anything
bigger (DCF, comps, sensitivity) belongs in the valuation/ package,
where COMPUTE already runs it.
"""

from __future__ import annotations

from collections.abc import Callable
from numbers import Real

from .schemas import BundleFact, ComputedSource


class DerivationError(RuntimeError):
    """Raised when a derivation cannot run — missing inputs, divide-by-zero,
    non-numeric facts. The mint step catches this and the section is routed
    back through WRITE with the failure surfaced."""


def _scalar(fact: BundleFact) -> float:
    if not isinstance(fact.value, Real) or isinstance(fact.value, bool):
        raise DerivationError(
            f"Fact '{fact.id}' is non-numeric (value={fact.value!r}); "
            "derivations require scalar numeric inputs."
        )
    return float(fact.value)


def growth_rate(current: BundleFact, prior: BundleFact, *, new_id: str, label: str) -> BundleFact:
    """(current - prior) / prior. Returns a fraction (0.25 = 25%)."""
    cur_v = _scalar(current)
    prev_v = _scalar(prior)
    if prev_v == 0:
        raise DerivationError(
            f"growth_rate: prior value is zero for facts ({current.id}, {prior.id}); cannot divide."
        )
    return BundleFact(
        id=new_id,
        label=label,
        value=(cur_v - prev_v) / prev_v,
        unit="percent",
        source=ComputedSource(method="growth_rate", derived_from=[current.id, prior.id]),
    )


def yoy_delta(current: BundleFact, prior: BundleFact, *, new_id: str, label: str) -> BundleFact:
    """current - prior. Absolute change in the input's unit."""
    cur_v = _scalar(current)
    prev_v = _scalar(prior)
    return BundleFact(
        id=new_id,
        label=label,
        value=cur_v - prev_v,
        unit=current.unit,
        source=ComputedSource(method="yoy_delta", derived_from=[current.id, prior.id]),
    )


def ratio(numerator: BundleFact, denominator: BundleFact, *, new_id: str, label: str) -> BundleFact:
    """numerator / denominator. Returns a fraction; unit defaults to None
    so the formatter renders a clean number (caller may set 'percent' /
    'x' downstream if appropriate)."""
    num_v = _scalar(numerator)
    den_v = _scalar(denominator)
    if den_v == 0:
        raise DerivationError(
            f"ratio: denominator value is zero for facts "
            f"({numerator.id}, {denominator.id}); cannot divide."
        )
    return BundleFact(
        id=new_id,
        label=label,
        value=num_v / den_v,
        unit=None,
        source=ComputedSource(method="ratio", derived_from=[numerator.id, denominator.id]),
    )


# Registry the mint step looks methods up in. Keep keys in sync with
# the DERIVE marker grammar documented in WRITE_SYSTEM_PROMPT.
DERIVATION_REGISTRY: dict[str, Callable[..., BundleFact]] = {
    "growth_rate": growth_rate,
    "yoy_delta": yoy_delta,
    "ratio": ratio,
}
