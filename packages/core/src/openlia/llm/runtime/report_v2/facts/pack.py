from __future__ import annotations

from dataclasses import dataclass

from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import Fact, ManifestEntry


class PayloadView:
    """Indexed view over the manifest, exposed to extractor functions."""

    def __init__(self, manifest: list[ManifestEntry], *, subject_ticker: str | None = None) -> None:
        self._by_identifier: dict[str, ManifestEntry] = {e.identifier: e for e in manifest}
        self.subject_ticker = subject_ticker

    def by_identifier(self, identifier: str):
        return self._by_identifier[identifier].raw_payload

    def manifest_id_for(self, identifier: str) -> int:
        return self._by_identifier[identifier].id

    def has(self, identifier: str) -> bool:
        return identifier in self._by_identifier

    def fundamentals_identifiers(self) -> list[str]:
        """All manifest identifiers that are fundamentals fetches, in manifest order."""
        return [k for k in self._by_identifier if k.startswith("get_fundamentals_data/")]

    @staticmethod
    def _ticker_from_identifier(identifier: str) -> str:
        suffix = identifier.removeprefix("get_fundamentals_data/")
        return suffix.split(".", 1)[0]

    def subject_fundamentals_identifier(self) -> str:
        """Return the manifest identifier for the subject's fundamentals.

        Prefers an exact subject-ticker match when `subject_ticker` is set;
        otherwise falls back to the first fundamentals identifier in the manifest.
        """
        candidates = self.fundamentals_identifiers()
        if not candidates:
            raise KeyError("no manifest entry starting with 'get_fundamentals_data/'")
        if self.subject_ticker is not None:
            wanted = self.subject_ticker.upper()
            for c in candidates:
                if self._ticker_from_identifier(c).upper() == wanted:
                    return c
        return candidates[0]

    def peer_fundamentals(self) -> list[tuple[str, str]]:
        """Return [(ticker, identifier), ...] for every non-subject fundamentals entry."""
        subject_id = None
        try:
            subject_id = self.subject_fundamentals_identifier()
        except KeyError:
            return []
        out: list[tuple[str, str]] = []
        for ident in self.fundamentals_identifiers():
            if ident == subject_id:
                continue
            out.append((self._ticker_from_identifier(ident), ident))
        return out


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
    subject_ticker: str | None = None,
) -> FactsPack:
    order = registry.resolution_order(requested_facts)
    payloads = PayloadView(manifest, subject_ticker=subject_ticker)
    facts: dict[str, Fact] = {}
    for name in order:
        entry = registry.get(name)
        fact = entry.fn(payloads, facts)
        if fact.name != name:
            raise ValueError(f"extractor for {name!r} returned fact named {fact.name!r}")
        facts[name] = fact
    return FactsPack(facts=facts)
