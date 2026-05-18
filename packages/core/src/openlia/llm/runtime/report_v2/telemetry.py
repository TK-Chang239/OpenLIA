from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import SectionResult


@dataclass
class WaveTimings:
    durations_ms: dict[str, int] = field(default_factory=dict)


@dataclass
class ReportTelemetry:
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    section_states: Counter = field(default_factory=Counter)
    proposed_facts: dict[str, list[str]] = field(default_factory=dict)
    wave_timings: WaveTimings = field(default_factory=WaveTimings)
    search_sentinels: dict[str, list[str]] = field(default_factory=dict)
    auto_repair_fixes: Counter = field(default_factory=Counter)

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

    def snapshot(self) -> dict[str, Any]:
        return {
            "sections": dict(self.sections),
            "section_states": dict(self.section_states),
            "proposed_facts": dict(self.proposed_facts),
            "wave_ms": dict(self.wave_timings.durations_ms),
            "search_sentinels": dict(self.search_sentinels),
            "auto_repair_fixes": dict(self.auto_repair_fixes),
        }
