from __future__ import annotations

import re
from datetime import datetime

from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue

TOMBSTONE_PATTERNS = [
    r"\[placeholder\]",
    r"\[TODO\]",
    r"\bTBD\b",
    r"\bI cannot\b",
    r"\bas an AI\b",
    r"\[\s*to be filled\s*\]",
]

_COMPILED_TOMBSTONES = [re.compile(p) for p in TOMBSTONE_PATTERNS]
_CITE_MARKER_RE = re.compile(r"\[c:([a-zA-Z0-9_]+)\]")
_FY_YEAR_RE = re.compile(r"FY(20\d{2})")


def detect_block_shape(section_id: str, blocks: list[dict]) -> list[VerifierIssue]:
    issues: list[VerifierIssue] = []
    for b in blocks:
        t = b.get("type")
        if t == "prose" and not (b.get("text") or "").strip():
            issues.append(
                VerifierIssue(
                    issue_type="block_shape",
                    section_id=section_id,
                    severity="blocker",
                    evidence="empty prose block",
                    suggested_fix="Populate the prose block or remove it.",
                    detector="deterministic",
                )
            )
        elif t == "table" and not b.get("headers"):
            issues.append(
                VerifierIssue(
                    issue_type="block_shape",
                    section_id=section_id,
                    severity="blocker",
                    evidence="table missing headers",
                    suggested_fix="Add a headers field to the table block.",
                    detector="deterministic",
                )
            )
    return issues


def detect_tombstone(section_id: str, blocks: list[dict]) -> list[VerifierIssue]:
    issues: list[VerifierIssue] = []
    for b in blocks:
        text = b.get("text", "") if isinstance(b.get("text"), str) else ""
        for pat, compiled in zip(TOMBSTONE_PATTERNS, _COMPILED_TOMBSTONES, strict=True):
            m = compiled.search(text)
            if m:
                snippet = text[max(0, m.start() - 20) : m.end() + 20]
                issues.append(
                    VerifierIssue(
                        issue_type="tombstone",
                        section_id=section_id,
                        severity="blocker",
                        evidence=f"matched {pat!r} at ...{snippet}...",
                        suggested_fix="Replace placeholder with explicit prose or remove sentence.",
                        detector="deterministic",
                    )
                )
                break  # one issue per block
    return issues


def _extract_fy_years(text: str) -> set[int]:
    return {int(m.group(1)) for m in _FY_YEAR_RE.finditer(text)}


def detect_year_slip(
    section_id: str,
    blocks: list[dict],
    citations: dict,
) -> list[VerifierIssue]:
    issues: list[VerifierIssue] = []
    for b in blocks:
        text = b.get("text", "")
        fy_years = _extract_fy_years(text)
        if not fy_years:
            continue
        for cite_id in _CITE_MARKER_RE.findall(text):
            cite = citations.get(cite_id)
            if not cite:
                continue
            try:
                retrieved_at = cite.get("retrieved_at", "")
                ret = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
            except Exception:
                continue
            for y in fy_years:
                if abs(ret.year - y) >= 2:
                    issues.append(
                        VerifierIssue(
                            issue_type="year_slip",
                            section_id=section_id,
                            severity="blocker",
                            evidence=(
                                f"FY{y} referenced; citation [c:{cite_id}] retrieved {ret.year}"
                            ),
                            suggested_fix=(
                                f"Update year reference to align with citation, "
                                f"or recite from FY{y} source."
                            ),
                            detector="deterministic",
                        )
                    )
                    break  # one issue per citation per block
    return issues


def detect_citation_unresolved(
    section_id: str,
    blocks: list[dict],
    pool_citation_ids: set[str],
) -> list[VerifierIssue]:
    issues: list[VerifierIssue] = []
    for b in blocks:
        text = b.get("text", "")
        for cite_id in _CITE_MARKER_RE.findall(text):
            if cite_id not in pool_citation_ids:
                issues.append(
                    VerifierIssue(
                        issue_type="citation_unresolved",
                        section_id=section_id,
                        severity="blocker",
                        evidence=f"marker [c:{cite_id}] not in research_pool",
                        suggested_fix=(
                            "Re-cite from an actual research entry; this ID does not exist."
                        ),
                        detector="deterministic",
                    )
                )
    return issues


def detect_citation_orphaned(
    used_ids: set[str],
    pool_citation_ids: set[str],
) -> list[VerifierIssue]:
    issues: list[VerifierIssue] = []
    for cid in pool_citation_ids - used_ids:
        issues.append(
            VerifierIssue(
                issue_type="citation_orphaned",
                section_id=None,
                severity="warning",
                evidence=f"citation {cid} in pool but never embedded",
                suggested_fix=None,
                detector="deterministic",
            )
        )
    return issues


def detect_artifact_missing(
    required_artifact_ids: set[str],
    embedded_artifact_ids: set[str],
) -> list[VerifierIssue]:
    issues: list[VerifierIssue] = []
    for aid in required_artifact_ids - embedded_artifact_ids:
        issues.append(
            VerifierIssue(
                issue_type="artifact_missing",
                section_id=None,
                severity="blocker",
                evidence=f"required artifact {aid} was built but never embedded",
                suggested_fix=f"Add {{{{artifact:{aid}}}}} to the appropriate section.",
                detector="deterministic",
            )
        )
    return issues
