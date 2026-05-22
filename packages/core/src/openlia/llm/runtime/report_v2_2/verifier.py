"""Stage 8 verifier for v2.2 materialized sections.

Per artifact-injection §8. Reads runtime Pydantic models (not just strings).
Operates on MaterializedSection + drafted markdown + raw helper_outputs.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .enums import VerifierIssueType
from .materialize import MaterializedSection
from .verifier_models import VerifierIssue

if TYPE_CHECKING:
    from .section_plan import ReportSectionPlan

_VERIFIER_HELPER = "__verifier__"

# Regex matching decimal / integer numbers in prose.
_NUMBER_RE = re.compile(r"\b\d[\d,\.]*%?\b")

# Regex matching FY year tokens: FY2023, FY24, fy2025, etc.
_FY_YEAR_RE = re.compile(r"\bFY(20)?(\d{2})\b", re.IGNORECASE)

# Regex matching markdown footnote-style citation markers: [^foo] or [^foo_bar].
_CITATION_MARKER_RE = re.compile(r"\[\^([a-zA-Z0-9_\-]+)\]")


class Verifier:
    """Checks a drafted section against the materialized artifacts and helper outputs.

    Per artifact-injection §8. Returns a list of VerifierIssue. Empty list = clean.
    """

    def verify(
        self,
        materialized: MaterializedSection,
        drafted_markdown: str,
        helper_outputs: dict[str, Any],
        *,
        min_words: int | None = None,
        tolerance_pct: int | None = None,
        word_budget: int | None = None,
        as_of_year: int | None = None,
        section_plan: ReportSectionPlan | None = None,
    ) -> list[VerifierIssue]:
        """Run all verifier checks and return collected issues.

        Checks performed (PR 0.3 minimum set + Phase 2 exit gate additions):
        - WORD_COUNT_OUT_OF_RANGE via CONTENT_TOO_SPARSE / DIRECTIVE_UNMET
        - MIN_WORDS_NOT_MET via CONTENT_TOO_SPARSE detail_code
        - BLOCK_PLAN_ARTIFACT_MISSING: carry from materialization_warnings
        - BLOCK_ARTIFACT_TOO_LARGE: carry from materialization_warnings
        - BLOCK_SECTION_PLAN_INVALID: carry from materialization_warnings
        - YEAR_SLIP: FY year tokens that drift >= 2 years from as_of_year
        - CITATION_UNRESOLVED: [^marker] with no matching rendered artifact
        - CITATION_ORPHANED: rendered artifact never cited in draft
        - HELPER_UNAVAILABLE: section_plan references unregistered helper
        - INCOHERENT_PROSE: run-on sentences, repeated words, verbless paragraphs
        """
        issues: list[VerifierIssue] = []

        # --- 1. Carry materialization warnings through ---
        for warn in materialized.materialization_warnings:
            issues.append(warn)

        # --- 2. Word count checks ---
        word_count = _count_words(drafted_markdown)
        issues.extend(
            self._check_word_count(
                word_count=word_count,
                min_words=min_words,
                tolerance_pct=tolerance_pct,
                word_budget=word_budget,
                section_id=materialized.section_id,
            )
        )

        # --- 3. Cited artifact presence check ---
        issues.extend(
            self._check_artifact_citations(
                materialized=materialized,
                drafted_markdown=drafted_markdown,
            )
        )

        # --- 4. Numeric reconciliation (light pass) ---
        issues.extend(
            self._check_numeric_grounding(
                materialized=materialized,
                drafted_markdown=drafted_markdown,
                helper_outputs=helper_outputs,
            )
        )

        # --- 5. Year slip ---
        issues.extend(
            self._check_year_slip(
                materialized=materialized,
                drafted_markdown=drafted_markdown,
                as_of_year=as_of_year,
            )
        )

        # --- 6. Citation unresolved ---
        issues.extend(
            self._check_citation_unresolved(
                materialized=materialized,
                drafted_markdown=drafted_markdown,
            )
        )

        # --- 7. Citation orphaned ---
        issues.extend(
            self._check_citation_orphaned(
                materialized=materialized,
                drafted_markdown=drafted_markdown,
            )
        )

        # --- 8. Helper availability ---
        issues.extend(
            self._check_helper_availability(
                materialized=materialized,
                section_plan=section_plan,
            )
        )

        # --- 9. Prose coherence ---
        issues.extend(
            self._check_prose_coherence(
                drafted_markdown=drafted_markdown,
                section_id=materialized.section_id,
            )
        )

        return issues

    def _check_word_count(
        self,
        *,
        word_count: int,
        min_words: int | None,
        tolerance_pct: int | None,
        word_budget: int | None,
        section_id: str,
    ) -> list[VerifierIssue]:
        issues: list[VerifierIssue] = []

        if min_words is not None and word_count < min_words:
            issues.append(
                VerifierIssue(
                    type=VerifierIssueType.CONTENT_TOO_SPARSE,
                    detail_code="min_words_not_met",
                    severity="blocking",
                    helper=_VERIFIER_HELPER,
                    detail=(
                        f"Section {section_id!r}: drafted {word_count} words, "
                        f"minimum required {min_words}."
                    ),
                )
            )

        if word_budget is not None and tolerance_pct is not None:
            lower = word_budget * (1 - tolerance_pct / 100)
            upper = word_budget * (1 + tolerance_pct / 100)
            if word_count < lower or word_count > upper:
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.DIRECTIVE_UNMET,
                        detail_code="word_count_out_of_range",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {section_id!r}: drafted {word_count} words, "
                            f"budget {word_budget} ± {tolerance_pct}% "
                            f"(range [{lower:.0f}, {upper:.0f}])."
                        ),
                    )
                )

        return issues

    def _check_artifact_citations(
        self,
        *,
        materialized: MaterializedSection,
        drafted_markdown: str,
    ) -> list[VerifierIssue]:
        """Check that every materialized artifact is referenced in the draft."""
        issues: list[VerifierIssue] = []
        for art in materialized.rendered_artifacts:
            # Light check: artifact_id appears somewhere in the draft.
            if art.artifact_id not in drafted_markdown:
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.ARTIFACT_MISSING,
                        detail_code="artifact_not_referenced",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {materialized.section_id!r}: "
                            f"artifact {art.artifact_id!r} was materialized but "
                            "does not appear to be referenced in the draft."
                        ),
                    )
                )
        return issues

    def _check_numeric_grounding(
        self,
        *,
        materialized: MaterializedSection,
        drafted_markdown: str,
        helper_outputs: dict[str, Any],
    ) -> list[VerifierIssue]:
        """Check that numbers in the draft appear in helper_outputs (light pass).

        A number in the draft that does not appear in any helper output's string
        representation is flagged as a potential hallucination. This is intentionally
        a soft/advisory check — the LLM may reformat numbers (e.g., $1.23B vs 1230).
        """
        issues: list[VerifierIssue] = []

        if not helper_outputs:
            return issues

        # Build a corpus of all numeric strings that appear in helper output.
        output_corpus = _stringify_values(helper_outputs)

        draft_numbers = _NUMBER_RE.findall(drafted_markdown)
        # Normalise: strip commas.
        draft_numbers_norm = [n.replace(",", "") for n in draft_numbers]

        hallucinated = [
            n
            for n in draft_numbers_norm
            if n not in output_corpus and len(n) > 2  # skip trivial 1-2 digit numbers
        ]

        if hallucinated:
            # Advisory — not blocking; numeric reformatting is common.
            issues.append(
                VerifierIssue(
                    type=VerifierIssueType.NUMERIC_INCONSISTENCY,
                    detail_code="number_not_in_helper_outputs",
                    severity="advisory",
                    helper=_VERIFIER_HELPER,
                    detail=(
                        f"Section {materialized.section_id!r}: "
                        f"{len(hallucinated)} number(s) in draft not found in "
                        f"helper outputs: {hallucinated[:5]}"
                        f"{'...' if len(hallucinated) > 5 else ''}."
                    ),
                )
            )

        return issues

    def _check_year_slip(
        self,
        *,
        materialized: MaterializedSection,
        drafted_markdown: str,
        as_of_year: int | None,
    ) -> list[VerifierIssue]:
        """Flag FY year tokens that drift >= 2 years from as_of_year.

        Per impl-plan §16 audit fix: YEAR_SLIP must be reachable.
        When as_of_year is None, fall back to inferring expected years from
        artifact raw_data keys / string values (best-effort); if neither
        source is available, skip check.
        """
        issues: list[VerifierIssue] = []

        # Extract FY years mentioned in the draft.
        fy_matches = _FY_YEAR_RE.findall(drafted_markdown)
        if not fy_matches:
            return issues

        draft_years: set[int] = set()
        for century_prefix, two_digit in fy_matches:
            if century_prefix:
                # e.g. FY2023 → 2023
                draft_years.add(int(century_prefix + two_digit))
            else:
                # e.g. FY24 → 2024
                draft_years.add(2000 + int(two_digit))

        # Determine reference year.
        ref_year: int | None = as_of_year

        if ref_year is None:
            # Infer from artifact raw_data: look for any 4-digit year-shaped integer.
            for art in materialized.rendered_artifacts:
                year_candidates = _extract_year_candidates(art.raw_data)
                if year_candidates:
                    ref_year = max(year_candidates)
                    break

        if ref_year is None:
            # No reference anchor available — cannot check.
            return issues

        for y in draft_years:
            if abs(y - ref_year) >= 2:
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.YEAR_SLIP,
                        detail_code="fy_year_drift",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {materialized.section_id!r}: "
                            f"draft references FY{y} but report as_of year is {ref_year} "
                            f"(drift = {abs(y - ref_year)} years)."
                        ),
                    )
                )

        return issues

    def _check_citation_unresolved(
        self,
        *,
        materialized: MaterializedSection,
        drafted_markdown: str,
    ) -> list[VerifierIssue]:
        """Flag [^marker] citations in draft that have no matching rendered artifact.

        Per impl-plan §16 audit fix: CITATION_UNRESOLVED must be reachable.
        A citation is considered resolved if the marker name matches any artifact_id
        in materialized.rendered_artifacts.
        """
        issues: list[VerifierIssue] = []

        markers = _CITATION_MARKER_RE.findall(drafted_markdown)
        if not markers:
            return issues

        known_artifact_ids = {art.artifact_id for art in materialized.rendered_artifacts}

        for marker in markers:
            if marker not in known_artifact_ids:
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.CITATION_UNRESOLVED,
                        detail_code="marker_no_artifact",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {materialized.section_id!r}: "
                            f"citation marker [^{marker}] has no matching artifact "
                            f"in materialized.rendered_artifacts."
                        ),
                    )
                )

        return issues

    def _check_citation_orphaned(
        self,
        *,
        materialized: MaterializedSection,
        drafted_markdown: str,
    ) -> list[VerifierIssue]:
        """Flag rendered artifacts that are never cited in the draft.

        Per impl-plan §16 audit fix: CITATION_ORPHANED must be reachable.
        Reverse of CITATION_UNRESOLVED: an artifact exists but the drafter never
        referenced it via a [^artifact_id] marker.
        """
        issues: list[VerifierIssue] = []

        cited_markers = set(_CITATION_MARKER_RE.findall(drafted_markdown))

        for art in materialized.rendered_artifacts:
            if art.artifact_id not in cited_markers:
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.CITATION_ORPHANED,
                        detail_code="artifact_never_cited",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {materialized.section_id!r}: "
                            f"artifact {art.artifact_id!r} was materialized but "
                            f"never cited via [^{art.artifact_id}] in the draft."
                        ),
                    )
                )

        return issues

    def _check_helper_availability(
        self,
        *,
        materialized: MaterializedSection,
        section_plan: ReportSectionPlan | None,
    ) -> list[VerifierIssue]:
        """Flag helpers referenced in section_plan that are not registered.

        Per impl-plan §16 audit fix: HELPER_UNAVAILABLE must be reachable.
        SectionArtifactRef.artifact_id is the helper name used as a lookup key;
        if that name is absent from list_helpers(), emit HELPER_UNAVAILABLE.
        This is a final-safety-net check (planner should catch this earlier).
        """
        issues: list[VerifierIssue] = []

        if section_plan is None:
            return issues

        from .tools.library_helpers import get_helper

        for section in section_plan.sections:
            if section.section_id != materialized.section_id:
                continue
            for ref in section.artifacts:
                helper_name = ref.artifact_id
                if get_helper(helper_name) is None:
                    issues.append(
                        VerifierIssue(
                            type=VerifierIssueType.HELPER_UNAVAILABLE,
                            detail_code="helper_not_registered",
                            severity="blocking",
                            helper=_VERIFIER_HELPER,
                            detail=(
                                f"Section {materialized.section_id!r}: "
                                f"helper {helper_name!r} referenced in section_plan "
                                f"is not registered in list_helpers()."
                            ),
                        )
                    )

        return issues

    def _check_prose_coherence(
        self,
        *,
        drafted_markdown: str,
        section_id: str,
    ) -> list[VerifierIssue]:
        """Detect prose-level structural issues via simple heuristics.

        Per impl-plan §16 audit fix: INCOHERENT_PROSE must be reachable.

        Heuristics (LLM-driven checks are out of scope):
        1. Run-on sentence: any sentence > 60 words.
        2. Repeated consecutive words: same word appears > 5 times in a row.
        3. Verbless paragraph: paragraph with no verb-like token (word ending
           in common verb suffixes: -ed, -ing, -es, -ize, -ise, -ate, or
           common irregular forms: is, are, was, were, has, have, had, do,
           does, did, be, been, being, will, would, can, could, may, might).
        """
        issues: list[VerifierIssue] = []

        # Strip code blocks to avoid false positives from code prose.
        clean_text = re.sub(r"```.*?```", "", drafted_markdown, flags=re.DOTALL)
        clean_text = re.sub(r"`[^`]+`", "", clean_text)

        # 1. Run-on sentence detection: split on sentence-ending punctuation.
        sentences = re.split(r"(?<=[.!?])\s+", clean_text)
        for sent in sentences:
            words = sent.split()
            if len(words) > 60:
                snippet = " ".join(words[:12]) + "..."
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.INCOHERENT_PROSE,
                        detail_code="run_on_sentence",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {section_id!r}: sentence with {len(words)} words "
                            f"exceeds 60-word heuristic threshold: {snippet!r}"
                        ),
                    )
                )

        # 2. Repeated consecutive word detection.
        repeated = re.search(r"\b(\w+)(?:\s+\1){5,}\b", clean_text, re.IGNORECASE)
        if repeated:
            issues.append(
                VerifierIssue(
                    type=VerifierIssueType.INCOHERENT_PROSE,
                    detail_code="repeated_consecutive_words",
                    severity="advisory",
                    helper=_VERIFIER_HELPER,
                    detail=(
                        f"Section {section_id!r}: word {repeated.group(1)!r} "
                        f"repeated consecutively more than 5 times."
                    ),
                )
            )

        # 3. Verbless paragraph detection.
        _VERB_RE = re.compile(
            r"\b("
            r"is|are|was|were|has|have|had|do|does|did|be|been|being"
            r"|will|would|can|could|may|might|shall|should|must"
            r"|\w+ed|\w+ing|\w+izes|\w+ises|\w+ates|\w+ens|\w+es"
            r")\b",
            re.IGNORECASE,
        )
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean_text) if p.strip()]
        for para in paragraphs:
            # Skip very short paragraphs (headings, single-word lines, etc.)
            words = para.split()
            if len(words) < 5:
                continue
            # Skip markdown heading lines.
            if para.startswith("#"):
                continue
            if not _VERB_RE.search(para):
                snippet = " ".join(words[:10])
                issues.append(
                    VerifierIssue(
                        type=VerifierIssueType.INCOHERENT_PROSE,
                        detail_code="verbless_paragraph",
                        severity="advisory",
                        helper=_VERIFIER_HELPER,
                        detail=(
                            f"Section {section_id!r}: paragraph appears to lack a verb: "
                            f"{snippet!r}..."
                        ),
                    )
                )

        return issues


def _count_words(text: str) -> int:
    """Approximate word count: split on whitespace."""
    return len(text.split())


def _stringify_values(obj: Any, _depth: int = 0) -> set[str]:
    """Recursively collect all scalar string representations from nested dicts/lists."""
    if _depth > 6:
        return set()
    result: set[str] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            result |= _stringify_values(v, _depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            result |= _stringify_values(item, _depth + 1)
    elif obj is not None:
        s = str(obj).replace(",", "")
        result.add(s)
        # Also add bare numeric tokens from within the string.
        result.update(_NUMBER_RE.findall(s))
    return result


_YEAR_CANDIDATE_RE = re.compile(r"\b(20\d{2})\b")


def _extract_year_candidates(obj: Any, _depth: int = 0) -> set[int]:
    """Scan a nested dict/list for 4-digit year-shaped integers (2000-2099)."""
    if _depth > 4:
        return set()
    result: set[int] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            result |= _extract_year_candidates(v, _depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            result |= _extract_year_candidates(item, _depth + 1)
    elif isinstance(obj, int) and 2000 <= obj <= 2099:
        result.add(obj)
    elif obj is not None:
        for m in _YEAR_CANDIDATE_RE.finditer(str(obj)):
            result.add(int(m.group(1)))
    return result
