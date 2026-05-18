from __future__ import annotations

from dataclasses import dataclass

from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import Fact, ManifestEntry


class PayloadView:
    """Indexed view over the manifest, exposed to extractor functions."""

    def __init__(self, manifest: list[ManifestEntry]) -> None:
        self._by_identifier: dict[str, ManifestEntry] = {e.identifier: e for e in manifest}

    def by_identifier(self, identifier: str):
        return self._by_identifier[identifier].raw_payload

    def manifest_id_for(self, identifier: str) -> int:
        return self._by_identifier[identifier].id

    def has(self, identifier: str) -> bool:
        return identifier in self._by_identifier


@dataclass
class FactsPack:
    facts: dict[str, Fact]

    def get(self, name: str) -> Fact:
        return self.facts[name]

    def slice_for(self, names: list[str]) -> dict[str, Fact]:
        out: dict[str, Fact] = {}
        for n in names:
            if n not in self.facts:
                raise KeyError(n)
            out[n] = self.facts[n]
        return out


def compile_pack(
    *,
    registry: FactRegistry,
    manifest: list[ManifestEntry],
    requested_facts: list[str],
) -> FactsPack:
    order = registry.resolution_order(requested_facts)
    payloads = PayloadView(manifest)
    facts: dict[str, Fact] = {}
    for name in order:
        entry = registry.get(name)
        fact = entry.fn(payloads, facts)
        if fact.name != name:
            raise ValueError(f"extractor for {name!r} returned fact named {fact.name!r}")
        facts[name] = fact
    return FactsPack(facts=facts)
