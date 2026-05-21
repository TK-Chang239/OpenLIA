from __future__ import annotations

from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue

LLM_VERIFIER_PROMPT = """
You are the LLM verifier. Read the section's blocks, the cited research pool,
and the model artifacts. Emit a JSON list of issues.

Issue types you may emit (LLM-only set):
  citation_missing, content_too_sparse, directive_unmet,
  factual_inconsistency, numeric_inconsistency, incoherent_prose

Each issue: {issue_type, severity (blocker|warning), evidence, suggested_fix}.
Provide suggested_fix where you can — high-signal fixes converge faster.

Do NOT emit structural or citation-id-resolution issues — those are caught
by deterministic detectors earlier.

Respond with a JSON object: {"issues": [...]}
""".strip()


class LLMVerifier:
    def __init__(self, llm) -> None:
        self._llm = llm

    def verify_section(
        self,
        section_id: str,
        blocks: list,
        research_pool,
        model_artifacts,
        directive: str,
    ) -> list[VerifierIssue]:
        try:
            raw = self._llm.call(
                system=LLM_VERIFIER_PROMPT,
                user={
                    "section_id": section_id,
                    "directive": directive,
                    "blocks": blocks,
                    "research_pool_index": {
                        k: v[:200] for k, v in research_pool.findings_by_strand.items()
                    },
                    "artifacts_index": [
                        {"id": a.spec.id, "description": a.spec.description}
                        for a in model_artifacts
                    ],
                },
            )
            return [
                VerifierIssue(detector="llm", section_id=section_id, **i)
                for i in raw.get("issues", [])
            ]
        except Exception:
            return []
