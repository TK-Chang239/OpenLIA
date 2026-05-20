from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import SectionResult


@dataclass
class WaveTimings:
    durations_ms: dict[str, int] = field(default_factory=dict)


@dataclass
class CrossSectionFinding:
    check: str
    sections: str  # comma-joined section ids
    detail: str


@dataclass
class OmittedBlock:
    section_id: str
    block_type: str
    reason: str


@dataclass
class ReportTelemetry:
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    section_states: Counter = field(default_factory=Counter)
    proposed_facts: dict[str, list[str]] = field(default_factory=dict)
    wave_timings: WaveTimings = field(default_factory=WaveTimings)
    search_sentinels: dict[str, list[str]] = field(default_factory=dict)
    auto_repair_fixes: Counter = field(default_factory=Counter)
    cross_section_findings: list[CrossSectionFinding] = field(default_factory=list)
    omitted_blocks: list[OmittedBlock] = field(default_factory=list)
    freshness_banner: dict[str, Any] | None = None

    def record_section(self, result: SectionResult) -> None:
        self.sections[result.section_id] = {
            "state": result.state.value,
            "attempts": result.attempts,
            "validation_errors": list(result.validation_errors),
        }
        self.section_states[result.state.value] += 1

    def record_proposed_facts(self, section_id: str, fact_names: list[str]) -> None:
        if fact_names:
            self.proposed_facts.setdefault(section_id, []).extend(fact_names)

    def record_wave(self, wave_name: str, *, duration_ms: int) -> None:
        self.wave_timings.durations_ms[wave_name] = duration_ms

    def record_search_sentinel(self, section_id: str, query: str) -> None:
        self.search_sentinels.setdefault(section_id, []).append(query)

    def record_auto_repair(self, fix_label: str) -> None:
        self.auto_repair_fixes[fix_label] += 1

    def record_cross_section_finding(self, *, check: str, sections: str, detail: str) -> None:
        self.cross_section_findings.append(
            CrossSectionFinding(check=check, sections=sections, detail=detail)
        )

    def record_omitted_block(self, section_id: str, block_type: str, reason: str) -> None:
        self.omitted_blocks.append(
            OmittedBlock(section_id=section_id, block_type=block_type, reason=reason)
        )

    def record_freshness_banner(
        self,
        *,
        oldest_data_as_of: str | None,
        violations: list[dict[str, Any]],
        override: bool,
    ) -> None:
        """Record the freshness banner block for the cover/manifest surface.

        Surfaced via the schema's telemetry dict so the renderer can show a
        "data as of <oldest_date>" badge and an explicit STALE DATA banner
        when the runner was invoked with `freshness_override=True`."""
        self.freshness_banner = {
            "oldest_data_as_of": oldest_data_as_of,
            "violations": violations,
            "override": override,
        }

    def snapshot(self) -> dict[str, Any]:
        omitted_counts: Counter = Counter()
        for ob in self.omitted_blocks:
            omitted_counts[f"{ob.section_id}/{ob.block_type}"] += 1
        return {
            "sections": dict(self.sections),
            "section_states": dict(self.section_states),
            "proposed_facts": dict(self.proposed_facts),
            "wave_ms": dict(self.wave_timings.durations_ms),
            "search_sentinels": dict(self.search_sentinels),
            "auto_repair_fixes": dict(self.auto_repair_fixes),
            "cross_section_findings": [
                {"check": f.check, "sections": f.sections, "detail": f.detail}
                for f in self.cross_section_findings
            ],
            "omitted_blocks": [
                {"section_id": ob.section_id, "block_type": ob.block_type, "reason": ob.reason}
                for ob in self.omitted_blocks
            ],
            "omitted_block_counts": dict(omitted_counts),
            "freshness_banner": self.freshness_banner,
        }
