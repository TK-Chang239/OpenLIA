from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.types import ManifestEntry, ManifestKind


@dataclass
class Manifest:
    entries: list[ManifestEntry] = field(default_factory=list)
    _by_identifier: dict[str, ManifestEntry] = field(default_factory=dict)

    def append(
        self,
        *,
        kind: ManifestKind,
        provider: str,
        identifier: str,
        raw_payload: Any,
        retrieved_at: Any,
    ) -> ManifestEntry:
        if identifier in self._by_identifier:
            return self._by_identifier[identifier]
        entry = ManifestEntry(
            id=len(self.entries) + 1,
            kind=kind,
            provider=provider,
            identifier=identifier,
            raw_payload=raw_payload,
            retrieved_at=retrieved_at,
        )
        self.entries.append(entry)
        self._by_identifier[identifier] = entry
        return entry

    def resolve(self, marker_id: int) -> ManifestEntry:
        if not (1 <= marker_id <= len(self.entries)):
            raise KeyError(f"manifest id {marker_id} out of range (1..{len(self.entries)})")
        return self.entries[marker_id - 1]

    def as_prompt_list(self) -> str:
        return "\n".join(f"[{e.id}] {e.provider}/{e.identifier}" for e in self.entries)

    def __len__(self) -> int:
        return len(self.entries)
