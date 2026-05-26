"""Resolve inline DERIVE/ESTIMATE markers into BundleFacts.

WriteStage calls into this between ``client.write`` and ``_coerce_section``.
Each resolved marker becomes a real BundleFact (ComputedSource for derive,
EstimateSource for estimate) that the engine adds to ``state.bundle`` and a
``{{CITE:<new_id>}}`` marker in the body. After this step runs, every
numeric claim a writer made traces to a typed origin, and VERIFY's
deterministic uncited-number check has nothing legitimate left to flag.

Dedup rule: if a marker's ``new_id`` is already present in the bundle and
the existing fact was minted by an identical call (same method + same
derived_from for derive; same basis + value for estimate), reuse it. If
the id exists with different content, raise — silent overwrite would
break the same-figure-everywhere invariant.
"""

from __future__ import annotations

import logging
import re

from ..derivations import DERIVATION_REGISTRY, DerivationError
from ..schemas import (
    DERIVE_RE,
    ESTIMATE_RE,
    BundleFact,
    ComputedSource,
    EstimateSource,
    ResearchBundle,
    SectionMandate,
)

log = logging.getLogger(__name__)


class MintError(RuntimeError):
    """Raised when a marker cannot be resolved. Routed back through WRITE."""


def mint_inline_facts(
    body: str,
    bundle: ResearchBundle,
    mandate: SectionMandate,
) -> tuple[str, list[BundleFact]]:
    """Return (rewritten_body, new_facts).

    Walks DERIVE markers first, then ESTIMATE markers. Both are replaced
    by ``{{CITE:<new_id>}}`` in the returned body. ``new_facts`` carries
    every BundleFact the caller must add to ``state.bundle`` — caller is
    responsible for the insertion (matches the COMPUTE pattern of
    rebuilding the bundle via ResearchBundle constructor so the validator
    re-runs over the combined facts).
    """
    new_facts: list[BundleFact] = []
    # DERIVE runs before ESTIMATE so DERIVE-minted facts are visible to subsequent
    # markers; the shared seen_markers dict catches cross-type new_id collisions.
    seen_markers: dict[str, str] = {}

    # 1) DERIVE
    def _derive_sub(m: re.Match[str]) -> str:
        method_name, inputs_csv, new_id = m.group(1), m.group(2), m.group(3)
        input_ids = [s for s in inputs_csv.split(",") if s]
        if method_name not in DERIVATION_REGISTRY:
            raise MintError(
                f"DERIVE: unknown method '{method_name}' in section "
                f"'{mandate.section_id}'. Known: {sorted(DERIVATION_REGISTRY)}."
            )
        for fid in input_ids:
            if fid not in bundle.facts:
                raise MintError(
                    f"DERIVE: input fact '{fid}' not in bundle "
                    f"(section '{mandate.section_id}', method '{method_name}')."
                )
        raw = m.group(0)
        if new_id in seen_markers:
            if seen_markers[new_id] == raw:
                return f"{{{{CITE:{new_id}}}}}"
            raise MintError(
                f"DERIVE: new_id '{new_id}' used by two different markers "
                f"in section '{mandate.section_id}'. Each new_id must be unique to "
                f"one marker — pick distinct ids."
            )
        if new_id in bundle.facts:
            existing = bundle.facts[new_id]
            if _derive_matches_existing(existing, method_name, input_ids):
                # Documented dedup-on-identity: an upstream stage (RESEARCH,
                # COMPUTE, or an earlier WRITE mandate) already minted the
                # exact same fact. Reuse silently rather than raise — the
                # writer's intended math is identical, and forcing a unique
                # id here would scatter duplicate values across the bundle
                # under near-identical names. The CITE marker still
                # resolves; `new_facts` stays empty for this marker so the
                # WriteStage `state.bundle.add` loop does not try to insert
                # a duplicate.
                log.info(
                    "DERIVE dedup: new_id %r already minted identically "
                    "upstream (section %r). Reusing the existing fact.",
                    new_id,
                    mandate.section_id,
                )
                seen_markers[new_id] = m.group(0)
                return f"{{{{CITE:{new_id}}}}}"
            raise MintError(
                f"DERIVE: new_id '{new_id}' collides with an existing bundle fact "
                f"in section '{mandate.section_id}' that was minted differently "
                f"(your call: {method_name}({','.join(input_ids)}); existing source: "
                f"{type(existing.source).__name__}"
                f"{_describe_computed(existing.source)}). Pick a unique id, or use "
                f"{{{{CITE:{new_id}}}}} to reference the existing fact instead of deriving."
            )
        try:
            fact = DERIVATION_REGISTRY[method_name](
                *[bundle.facts[fid] for fid in input_ids],
                new_id=new_id,
                label=_label_from_id(new_id),
            )
        except DerivationError as exc:
            # Soft-fail: the writer LLM emitted a derive whose inputs the
            # registered method cannot run on — most commonly a ratio
            # against a non-scalar fact (BundleSeries for a segment
            # breakdown or a time-series), or a divide-by-zero. Failing
            # the whole stage over one bad marker drops the entire
            # report; instead, fall back to a CITE on the first input
            # and let the section ship. The input was already confirmed
            # present in the bundle on the existence check above, so
            # the fallback CITE is guaranteed to resolve. VERIFY's
            # deterministic uncited-number check still picks up
            # anything the writer's prose left dangling.
            fallback_id = input_ids[0]
            log.warning(
                "DERIVE soft-fail: %s on inputs %s in section %r — "
                "falling back to {{CITE:%s}}. Cause: %s",
                method_name,
                list(input_ids),
                mandate.section_id,
                fallback_id,
                exc,
            )
            seen_markers[new_id] = raw
            return f"{{{{CITE:{fallback_id}}}}}"
        new_facts.append(fact)
        seen_markers[new_id] = raw
        return f"{{{{CITE:{new_id}}}}}"

    body = DERIVE_RE.sub(_derive_sub, body)

    # 2) ESTIMATE
    def _estimate_sub(m: re.Match[str]) -> str:
        new_id, value_str, unit, basis = m.group(1), m.group(2), m.group(3), m.group(4)
        value = float(value_str)
        raw = m.group(0)
        if new_id in seen_markers:
            if seen_markers[new_id] == raw:
                return f"{{{{CITE:{new_id}}}}}"
            raise MintError(
                f"ESTIMATE: new_id '{new_id}' used by two different markers "
                f"in section '{mandate.section_id}'. Each new_id must be unique to "
                f"one marker — pick distinct ids."
            )
        if new_id in bundle.facts:
            existing = bundle.facts[new_id]
            if _estimate_matches_existing(existing, value, unit or None, basis.strip()):
                # Same docstring contract as DERIVE dedup: an earlier
                # stage (SYNTHESIZE or an earlier WRITE mandate) already
                # minted this exact estimate. Reuse instead of raising.
                log.info(
                    "ESTIMATE dedup: new_id %r already minted identically "
                    "upstream (section %r). Reusing the existing fact.",
                    new_id,
                    mandate.section_id,
                )
                seen_markers[new_id] = m.group(0)
                return f"{{{{CITE:{new_id}}}}}"
            raise MintError(
                f"ESTIMATE: new_id '{new_id}' collides with an existing bundle "
                f"fact in section '{mandate.section_id}' that was minted differently. "
                f"Pick a unique id, or use {{{{CITE:{new_id}}}}} to reference the "
                f"existing fact instead of re-estimating."
            )
        fact = BundleFact(
            id=new_id,
            label=_label_from_id(new_id),
            value=value,
            unit=unit or None,
            source=EstimateSource(
                basis=basis.strip(),
                derived_from=[],
                stage="write",
            ),
        )
        new_facts.append(fact)
        seen_markers[new_id] = raw
        return f"{{{{CITE:{new_id}}}}}"

    body = ESTIMATE_RE.sub(_estimate_sub, body)

    return body, new_facts


def _label_from_id(fact_id: str) -> str:
    """fact_id 'rev_growth_yoy' -> 'Rev Growth Yoy'. Cheap, deterministic."""
    return fact_id.replace("_", " ").title()


def _derive_matches_existing(existing: BundleFact, method: str, input_ids: list[str]) -> bool:
    """True iff the existing fact was minted by an identical DERIVE call.

    Identity is method-equality plus order-preserving input list equality.
    Order matters semantically — `growth_rate(rev_fy25, rev_fy24)` and
    `growth_rate(rev_fy24, rev_fy25)` produce different numbers — so we
    compare lists, not sets. The value itself isn't compared: when method
    + inputs match, the derivation is deterministic and the value is
    guaranteed to agree.
    """
    source = existing.source
    if not isinstance(source, ComputedSource):
        return False
    return source.method == method and list(source.derived_from) == list(input_ids)


def _estimate_matches_existing(
    existing: BundleFact,
    value: float,
    unit: str | None,
    basis: str,
) -> bool:
    """True iff the existing fact is an identical EstimateSource entry.

    Value, unit, and basis must all match. Estimates are explicit
    judgment, so any divergence (different number, different unit,
    different rationale) means the writer disagrees with the prior
    estimate — which is a real conflict the runner must surface, not
    silently dedup.
    """
    source = existing.source
    if not isinstance(source, EstimateSource):
        return False
    return existing.value == value and (existing.unit or None) == unit and source.basis == basis


def _describe_computed(source: object) -> str:
    """Tail fragment for the DERIVE collision error message — exposes
    the existing fact's method + inputs when it is a ComputedSource so
    the writer (or a future repair tier) can see exactly what differs."""
    if isinstance(source, ComputedSource):
        return f", method={source.method!r}, derived_from={list(source.derived_from)}"
    return ""
