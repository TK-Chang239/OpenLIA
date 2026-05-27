"""VERIFY stage — last gate before ASSEMBLE.

Two layers of checks, cheap-to-expensive:

1. **Deterministic** (in Python, no LLM call):
   - `dangling_cite` — a `{{CITE:fact_id}}` whose fact_id is absent
     from the bundle. Should not happen in normal flow (PR5 WriteStage
     and PR4 SynthesizeStage both validate against this), but worth
     a defense-in-depth pass.
   - `broken_fig_ref` — a `{{FIG:chart_id}}` whose chart_id is absent
     from thesis.charts.
   - `uncited_number` — a digit-bearing token in body text that is
     not inside a CITE/FIG marker and not in the exempt set
     (years 1900-2099, fiscal-year tokens, ordinals, quarter tokens).
     After WRITE's mint step, every legitimate numeric should be a
     CITE marker; anything left is a fabrication.

2. **LLM-driven**: pass thesis + bundle + sections to the verifier
   client for coherence-level checks (`value_mismatch`,
   `cross_section_contradiction`, `redundancy`, `chart_text_mismatch`).
   The client returns a `VerifyResult`; we merge it with the
   deterministic findings into the final result on state.

The runner reads `state.verify_result.must_rewrite` and routes the
offending sections back to WRITE for one bounded retry.
"""

from __future__ import annotations

import re
from typing import Literal

from ..clients.verifier import VerifierClient, VerifierRequest
from ..schemas import (
    CITE_RE,
    FIG_RE,
    DataProviderSource,
    IssueKind,
    IssueSeverity,
    LaneCoverage,
    Outline,
    ReportThesis,
    ResearchBundle,
    VerifyIssue,
    VerifyResult,
    WebSource,
    WrittenSection,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext

# A digit-bearing token: optional leading $, then digits with optional
# decimal / thousands-comma, then optional magnitude or unit suffix.
# Examples matched: $60.9B, 1,200, 25%, 15x, 200, 18.5, 60.9, $1.2M.
_NUMERIC_TOKEN_RE = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?(?:[%xX]|[KkMmBbTt](?=\b|$))?")

# Token-level exempt patterns.
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_ORDINAL_SUFFIX_RE = re.compile(r"(?:st|nd|rd|th)\b", re.IGNORECASE)


class VerifyStage(Stage):
    slot = V23Slot.VERIFY

    def __init__(self, client: VerifierClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        thesis = self._require_thesis(state)
        bundle = self._require_bundle(state)
        if not state.sections:
            raise RuntimeError("VERIFY requires state.sections from WRITE.")

        deterministic = _deterministic_checks(state.sections, thesis, bundle)

        request = VerifierRequest(
            raw_prompt=state.raw_prompt,
            language=state.language,
            thesis=thesis,
            bundle=bundle,
            sections=list(state.sections),
            template=state.template,
        )
        from_llm = self._client.verify(request)

        data_coverage = (
            _lane_coverage(state.outline, bundle, lane="data")
            if state.outline is not None
            else None
        )
        web_coverage = (
            _lane_coverage(state.outline, bundle, lane="web") if state.outline is not None else None
        )
        state.verify_result = VerifyResult(
            issues=[*deterministic, *from_llm.issues],
            data_coverage=data_coverage,
            web_coverage=web_coverage,
        )
        return state

    @staticmethod
    def _require_thesis(state: ReportState) -> ReportThesis:
        if state.thesis is None:
            raise RuntimeError("VERIFY requires state.thesis from SYNTHESIZE.")
        return state.thesis

    @staticmethod
    def _require_bundle(state: ReportState) -> ResearchBundle:
        if state.bundle is None:
            raise RuntimeError("VERIFY requires state.bundle.")
        return state.bundle


def _deterministic_checks(
    sections: list[WrittenSection],
    thesis: ReportThesis,
    bundle: ResearchBundle,
) -> list[VerifyIssue]:
    """Walk every placeholder + every naked number; HIGH if integrity-violating."""
    bundle_fact_ids = set(bundle.facts.keys())
    chart_ids = {c.id for c in thesis.charts}

    issues: list[VerifyIssue] = []
    for section in sections:
        for fact_id in section.cited_fact_ids():
            if fact_id not in bundle_fact_ids:
                issues.append(
                    VerifyIssue(
                        section_id=section.section_id,
                        kind=IssueKind.DANGLING_CITE,
                        severity=IssueSeverity.HIGH,
                        detail=f"{{CITE:{fact_id}}} does not resolve in the bundle.",
                    )
                )
        for chart_id in section.figure_ids():
            if chart_id not in chart_ids:
                issues.append(
                    VerifyIssue(
                        section_id=section.section_id,
                        kind=IssueKind.BROKEN_FIG_REF,
                        severity=IssueSeverity.HIGH,
                        detail=f"{{FIG:{chart_id}}} does not match any chart spec.",
                    )
                )
    issues.extend(_check_uncited_numbers(sections))
    return issues


def _check_uncited_numbers(sections: list[WrittenSection]) -> list[VerifyIssue]:
    """Flag digit-bearing tokens that are neither inside a marker nor exempt.

    Strips CITE/FIG markers from a working copy of the body so the marker
    payloads cannot trigger the scan, then walks every numeric token in
    what remains and filters out the exempt classes (4-digit years,
    fiscal-year tokens, ordinals, quarter labels).
    """
    issues: list[VerifyIssue] = []
    for section in sections:
        stripped = FIG_RE.sub("", CITE_RE.sub("", section.body))
        violations: list[str] = []
        for match in _NUMERIC_TOKEN_RE.finditer(stripped):
            token = match.group(0)
            if _is_exempt(token, stripped, match.start(), match.end()):
                continue
            violations.append(token)
        if violations:
            joined = ", ".join(violations)
            issues.append(
                VerifyIssue(
                    section_id=section.section_id,
                    kind=IssueKind.UNCITED_NUMBER,
                    severity=IssueSeverity.HIGH,
                    detail=(
                        f"Numeric values not anchored to a fact: {joined}. "
                        f"Use {{{{CITE:<fact_id>}}}} for sourced numbers, "
                        f"{{{{DERIVE:<method>|<inputs>|<id>}}}} for derived "
                        f"numbers, or "
                        f"{{{{ESTIMATE:<id>|<value>|<unit>|<basis>}}}} for "
                        f"analyst judgment."
                    ),
                )
            )
    return issues


def _lane_coverage(
    outline: Outline,
    bundle: ResearchBundle,
    *,
    lane: Literal["data", "web"],
) -> LaneCoverage | None:
    """Count needs in a given lane and how many landed at least one
    expected fact id with provenance MATCHING the lane. Returns None
    when the outline emits no needs in this lane — the metric is N/A
    rather than zero.

    - data lane → ``DataProviderSource`` (EODHD).
    - web lane  → ``WebSource`` (open-web hit harvested from
      ``web_search`` citations).

    A need belongs to a lane iff its lane-specific id list is
    non-empty. A need is "satisfied" iff at least one of those ids
    exists in ``bundle.facts`` with a source instance matching the
    lane's provenance type. An id present in the bundle with the
    WRONG-lane provenance is NOT counted — that is the silent-
    substitution failure the metric is built to surface (e.g. model
    emits an id from ``web_fact_ids`` backed by EODHD news).
    """
    if lane == "data":
        in_lane = {
            fid for fid, fact in bundle.facts.items() if isinstance(fact.source, DataProviderSource)
        }
    else:
        in_lane = {fid for fid, fact in bundle.facts.items() if isinstance(fact.source, WebSource)}

    total = 0
    satisfied = 0
    for section in outline.sections:
        for need in section.data_needs:
            need_ids = need.data_fact_ids if lane == "data" else need.web_fact_ids
            if not need_ids:
                continue
            total += 1
            if any(fid in in_lane for fid in need_ids):
                satisfied += 1
    if total == 0:
        return None
    return LaneCoverage(total=total, satisfied=satisfied, pct=satisfied / total)


def _is_exempt(token: str, body: str, start: int, end: int) -> bool:
    # 4-digit year alone (1900-2099)
    if _YEAR_RE.match(token):
        return True
    # Fiscal-year token: the regex captures the digit tail of "FY2025";
    # check the two preceding characters in the body.
    if start >= 2 and body[start - 2 : start].upper() == "FY":
        return True
    # Quarter token: the regex captures the digit in "Q3"; check the prior char.
    if start >= 1 and body[start - 1].upper() == "Q":
        return True
    # Ordinal: the regex captures "3" in "3rd"; check the two trailing chars.
    if _ORDINAL_SUFFIX_RE.match(body[end : end + 2]):
        return True
    return False
