from __future__ import annotations

from dataclasses import dataclass, field

from openlia.llm.runtime.report_v2.pipeline.verifier_deterministic import (
    detect_block_shape,
    detect_citation_unresolved,
    detect_tombstone,
    detect_year_slip,
)
from openlia.llm.runtime.report_v2.pipeline.verifier_llm import LLMVerifier
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


@dataclass
class VerificationRound:
    round_num: int
    issues: list[VerifierIssue]


@dataclass
class SectionVerificationResult:
    section_id: str
    final_status: str  # "OK" | "DEGRADED"
    rounds: list[VerificationRound] = field(default_factory=list)
    all_issues_ever: list[VerifierIssue] = field(default_factory=list)


class Verifier:
    MAX_RETRIES = 3

    def __init__(
        self,
        llm_verifier: LLMVerifier,
        drafter,
        section_directives: dict[str, str],
    ) -> None:
        self._llm = llm_verifier
        self._drafter = drafter
        self._directives = section_directives

    def verify_with_retry(
        self,
        section_id: str,
        blocks: list,
        research_pool,
        model_artifacts,
        citations: dict,
        pool_citation_ids: set[str],
        required_artifact_ids: set[str],
        embedded_artifact_ids: set[str],
        retry_context: dict,
    ) -> SectionVerificationResult:
        result = SectionVerificationResult(section_id=section_id, final_status="OK")
        signatures: list[set[tuple[str | None, str]]] = []
        current_blocks = blocks

        for round_num in range(self.MAX_RETRIES + 1):
            issues: list[VerifierIssue] = []

            # deterministic detectors always run first
            issues += detect_block_shape(section_id, current_blocks)
            issues += detect_tombstone(section_id, current_blocks)
            issues += detect_year_slip(section_id, current_blocks, citations)
            issues += detect_citation_unresolved(section_id, current_blocks, pool_citation_ids)

            deterministic_blockers = [i for i in issues if i.severity == "blocker"]

            # LLM verifier runs only when no deterministic blockers exist
            if not deterministic_blockers:
                llm_issues = self._llm.verify_section(
                    section_id=section_id,
                    blocks=current_blocks,
                    research_pool=research_pool,
                    model_artifacts=model_artifacts,
                    directive=self._directives.get(section_id, ""),
                )
                issues += llm_issues

            result.rounds.append(VerificationRound(round_num=round_num, issues=issues))
            result.all_issues_ever.extend(issues)

            blockers = [i for i in issues if i.severity == "blocker"]
            if not blockers:
                result.final_status = "OK"
                return result

            # convergence check: identical blocker signature two rounds in a row
            sig: set[tuple[str | None, str]] = {(i.section_id, i.issue_type) for i in blockers}
            signatures.append(sig)
            if len(signatures) >= 2 and signatures[-1] == signatures[-2]:
                result.final_status = "DEGRADED"
                return result

            if round_num >= self.MAX_RETRIES:
                result.final_status = "DEGRADED"
                return result

            # call drafter for next round
            current_blocks = self._drafter.redraft_with_feedback(
                section_id=section_id,
                blockers=blockers,
                retry_context=retry_context,
            )

        result.final_status = "DEGRADED"
        return result
