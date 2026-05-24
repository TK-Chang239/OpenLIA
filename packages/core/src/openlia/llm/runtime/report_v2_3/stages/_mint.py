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
    seen_ids: set[str] = set()

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
        if new_id in seen_ids:
            return f"{{{{CITE:{new_id}}}}}"
        if new_id in bundle.facts:
            raise MintError(
                f"DERIVE: new_id '{new_id}' collides with an existing bundle fact "
                f"(section '{mandate.section_id}'). Pick a unique id."
            )
        try:
            fact = DERIVATION_REGISTRY[method_name](
                *[bundle.facts[fid] for fid in input_ids],
                new_id=new_id,
                label=_label_from_id(new_id),
            )
        except DerivationError as exc:
            raise MintError(
                f"DERIVE: {method_name} failed in section "
                f"'{mandate.section_id}': {exc}"
            ) from exc
        new_facts.append(fact)
        seen_ids.add(new_id)
        return f"{{{{CITE:{new_id}}}}}"

    body = DERIVE_RE.sub(_derive_sub, body)

    # 2) ESTIMATE
    def _estimate_sub(m: re.Match[str]) -> str:
        new_id, value_str, unit, basis = m.group(1), m.group(2), m.group(3), m.group(4)
        value = float(value_str)
        if new_id in seen_ids:
            return f"{{{{CITE:{new_id}}}}}"
        if new_id in bundle.facts:
            raise MintError(
                f"ESTIMATE: new_id '{new_id}' collides with an existing bundle "
                f"fact (section '{mandate.section_id}'). Pick a unique id."
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
        seen_ids.add(new_id)
        return f"{{{{CITE:{new_id}}}}}"

    body = ESTIMATE_RE.sub(_estimate_sub, body)

    return body, new_facts


def _label_from_id(fact_id: str) -> str:
    """fact_id 'rev_growth_yoy' -> 'Rev growth yoy'. Cheap, deterministic."""
    return fact_id.replace("_", " ").capitalize()
