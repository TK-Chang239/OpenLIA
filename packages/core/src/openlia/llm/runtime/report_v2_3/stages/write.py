"""WRITE stage — section-by-section drafting against the shared thesis.

Iterates `thesis.mandates` and asks the writer client for one
`WrittenSection` per mandate. Every writer call sees the *same* thesis,
which is what makes parallel-shape writing cohere instead of drift; only
the per-section slice of bundle + chart specs is filtered down.

After each call we apply placeholder discipline with graceful coercion
rather than raise-on-mismatch:
- ``section_id`` is forced to the mandate's id — the LLM occasionally
  echoes a different section_id from the thesis, but the mandate the
  writer was called with is the source of truth.
- ``{{CITE:<fact_id>}}`` markers that point outside the mandate's
  `relevant_fact_ids` are stripped from the body. The marker would
  render as a broken link anyway since the fact isn't in scope.
- ``{{FIG:<chart_id>}}`` markers outside the mandate's `chart_ids`
  are stripped for the same reason.

Between the writer call and ``_coerce_section`` we run
``mint_inline_facts`` to resolve any inline ``{{DERIVE:...}}`` and
``{{ESTIMATE:...}}`` markers into typed BundleFacts (ComputedSource /
EstimateSource) and replace them with ``{{CITE:<new_id>}}``. The minted
facts are appended to ``state.bundle`` immediately so subsequent
mandates can dedup against them, and the mandate handed to
``_coerce_section`` is extended with the newly minted ids so the
coercer does not strip the brand-new CITE markers as out-of-mandate.
After the loop the bundle is rebuilt once via ``ResearchBundle`` so the
derived_from validator runs over the combined facts (mirrors COMPUTE).

On a VERIFY-driven retry, `state.verify_result` is forwarded to the
client so the rewrite has the critique it must address. Sections that
were not flagged still get re-generated for simplicity — bounded retry
keeps this cheap (one rewrite per run at most).
"""

from __future__ import annotations

import logging
import re

from ..clients.writer import WriterClient, WriterRequest
from ..schemas import (
    BundleFact,
    ChartSpec,
    ReportThesis,
    ResearchBundle,
    SectionMandate,
    VerifyIssue,
    WrittenSection,
)
from ..slots import V23Slot
from ..state import ReportState
from ._mint import mint_inline_facts
from .base import Stage, StageContext

log = logging.getLogger(__name__)

_CITE_TOKEN = re.compile(r"\{\{CITE:([a-zA-Z0-9_]+)\}\}")
_FIG_TOKEN = re.compile(r"\{\{FIG:([a-zA-Z0-9_]+)\}\}")


class WriteStage(Stage):
    slot = V23Slot.WRITE

    def __init__(self, client: WriterClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        thesis = self._require_thesis(state)
        if state.bundle is None:
            raise RuntimeError("WRITE requires state.bundle.")

        prior_by_section: dict[str, WrittenSection] = {s.section_id: s for s in state.sections}
        critique_by_section: dict[str, list[VerifyIssue]] = (
            self._group_critique(state) if state.verify_result is not None else {}
        )
        chart_by_section: dict[str, list[ChartSpec]] = self._group_charts(thesis)

        new_sections: list[WrittenSection] = []
        minted_total: list[BundleFact] = []
        for mandate in thesis.mandates:
            relevant_facts = {
                fid: state.bundle.facts[fid]
                for fid in mandate.relevant_fact_ids
                if fid in state.bundle.facts
            }
            request = WriterRequest(
                section_mandate=mandate,
                thesis=thesis,
                language=state.language,
                length=state.length,
                relevant_facts=relevant_facts,
                assigned_charts=chart_by_section.get(mandate.section_id, []),
                prior_attempt=prior_by_section.get(mandate.section_id),
                critique=critique_by_section.get(mandate.section_id),
            )
            section = self._client.write(request)
            # Resolve inline DERIVE/ESTIMATE markers BEFORE coercion.
            # The minted facts get CITE markers in the body; we need
            # _coerce_section to allow them through, so we extend the
            # mandate's relevant_fact_ids for the coerce call only.
            new_body, new_facts = mint_inline_facts(section.body, state.bundle, mandate)
            if new_body != section.body:
                section = section.model_copy(update={"body": new_body})
            minted_total.extend(new_facts)
            # Add minted facts to the bundle now so subsequent mandates
            # can dedup against them. ResearchBundle.add raises on
            # duplicate ids, which is the desired behavior.
            for fact in new_facts:
                state.bundle.add(fact)
            extended_mandate = mandate.model_copy(
                update={
                    "relevant_fact_ids": [
                        *mandate.relevant_fact_ids,
                        *[f.id for f in new_facts],
                    ]
                }
            )
            section = self._coerce_section(section, extended_mandate)
            new_sections.append(section)

        # Rebuild bundle once so the validator's derived_from chain check
        # runs over the combined facts (mirrors compute.py's pattern).
        if minted_total:
            state.bundle = ResearchBundle(
                tickers=state.bundle.tickers,
                facts=dict(state.bundle.facts),
            )

        state.sections = new_sections
        return state

    # ------------------------------------------------------------------
    @staticmethod
    def _require_thesis(state: ReportState) -> ReportThesis:
        if state.thesis is None:
            raise RuntimeError("WRITE requires state.thesis from SYNTHESIZE.")
        return state.thesis

    @staticmethod
    def _group_charts(thesis: ReportThesis) -> dict[str, list[ChartSpec]]:
        out: dict[str, list[ChartSpec]] = {}
        for chart in thesis.charts:
            out.setdefault(chart.section_id, []).append(chart)
        return out

    @staticmethod
    def _group_critique(state: ReportState) -> dict[str, list[VerifyIssue]]:
        assert state.verify_result is not None
        out: dict[str, list[VerifyIssue]] = {}
        for issue in state.verify_result.issues:
            if issue.section_id is not None:
                out.setdefault(issue.section_id, []).append(issue)
        return out

    @staticmethod
    def _coerce_section(section: WrittenSection, mandate: SectionMandate) -> WrittenSection:
        """Force the section back into the mandate's contract.

        The writer was called with one specific mandate, so the mandate's
        section_id is the source of truth — the LLM occasionally echoes
        a different id from elsewhere in the thesis. Stray CITE/FIG
        markers that don't exist in the mandate's allowed sets are
        stripped from the body (rendering them would produce broken
        links anyway). This lets the run continue rather than failing
        the whole report on a label mismatch."""
        body = section.body
        section_id = section.section_id

        if section_id != mandate.section_id:
            log.warning(
                "WRITE: writer returned section_id %r for mandate %r; coercing.",
                section_id,
                mandate.section_id,
            )
            section_id = mandate.section_id

        allowed_facts = set(mandate.relevant_fact_ids)
        bad_cites = sorted(set(_CITE_TOKEN.findall(body)) - allowed_facts)
        if bad_cites:
            log.warning(
                "WRITE: section %r cites facts outside its mandate; stripping: %s",
                section_id,
                bad_cites,
            )
            body = _CITE_TOKEN.sub(
                lambda m: "" if m.group(1) in bad_cites else m.group(0),
                body,
            )

        allowed_figs = set(mandate.chart_ids)
        bad_figs = sorted(set(_FIG_TOKEN.findall(body)) - allowed_figs)
        if bad_figs:
            log.warning(
                "WRITE: section %r references charts outside its mandate; stripping: %s",
                section_id,
                bad_figs,
            )
            body = _FIG_TOKEN.sub(
                lambda m: "" if m.group(1) in bad_figs else m.group(0),
                body,
            )

        if section_id == section.section_id and body == section.body:
            return section
        return section.model_copy(update={"section_id": section_id, "body": body})
