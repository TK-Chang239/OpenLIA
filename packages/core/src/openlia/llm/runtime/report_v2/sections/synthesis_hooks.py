"""Synthesis hooks: per-section contract types and bundle rendering for synthesis prompts."""

from __future__ import annotations

from dataclasses import dataclass, field

from openlia.llm.runtime.report_v2.packer.parser import parse_section_file
from openlia.llm.runtime.report_v2.types import SectionResult


@dataclass
class SynthesisHook:
    section_id: str
    thesis_contribution: str
    bull_case_inputs: list[str] = field(default_factory=list)
    bear_case_inputs: list[str] = field(default_factory=list)


@dataclass
class SynthesisHooksBundle:
    hooks: list[SynthesisHook]

    def render(self) -> str:
        lines: list[str] = []
        for h in self.hooks:
            lines.append(f"{h.section_id}:")
            lines.append(f"  thesis_contribution: {h.thesis_contribution}")
            lines.append(f"  bull_case_inputs: {h.bull_case_inputs}")
            lines.append(f"  bear_case_inputs: {h.bear_case_inputs}")
            lines.append("")
        return "\n".join(lines).strip()


def extract_hooks_from_section_result(result: SectionResult) -> SynthesisHook | None:
    if not result.markdown:
        return None
    parsed = parse_section_file(result.markdown)
    raw = parsed.frontmatter.get("synthesis_hooks")
    if not raw:
        return None

    # Defensive: some writers wrap the single hook in a list — unwrap it.
    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict):
            raw = raw[0]
        else:
            reason = "list with no dict element" if raw else "empty list"
            print(
                f"[synthesis_hooks] section {result.section_id!r}: malformed/missing hooks"
                f" ({reason}); skipping",
                flush=True,
            )
            return None

    if not isinstance(raw, dict):
        print(
            f"[synthesis_hooks] section {result.section_id!r}: malformed/missing hooks"
            f" (expected dict, got {type(raw).__name__!r}); skipping",
            flush=True,
        )
        return None

    return SynthesisHook(
        section_id=result.section_id,
        thesis_contribution=raw.get("thesis_contribution") or "",
        bull_case_inputs=list(raw.get("bull_case_inputs") or []),
        bear_case_inputs=list(raw.get("bear_case_inputs") or []),
    )
