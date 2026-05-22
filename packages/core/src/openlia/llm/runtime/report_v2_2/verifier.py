"""Stage 8 verifier for v2.2 materialized sections.

Per artifact-injection §8. Reads runtime Pydantic models (not just strings).
Operates on MaterializedSection + drafted markdown + raw helper_outputs.
"""

from __future__ import annotations

import re
from typing import Any

from .enums import VerifierIssueType
from .materialize import MaterializedSection
from .verifier_models import VerifierIssue

_VERIFIER_HELPER = "__verifier__"

# Regex matching decimal / integer numbers in prose.
_NUMBER_RE = re.compile(r"\b\d[\d,\.]*%?\b")


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
    ) -> list[VerifierIssue]:
        """Run all verifier checks and return collected issues.

        Checks performed (PR 0.3 minimum set):
        - WORD_COUNT_OUT_OF_RANGE via CONTENT_TOO_SPARSE / DIRECTIVE_UNMET
        - MIN_WORDS_NOT_MET via CONTENT_TOO_SPARSE detail_code
        - BLOCK_PLAN_ARTIFACT_MISSING: carry from materialization_warnings
        - BLOCK_ARTIFACT_TOO_LARGE: carry from materialization_warnings
        - BLOCK_SECTION_PLAN_INVALID: carry from materialization_warnings
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
