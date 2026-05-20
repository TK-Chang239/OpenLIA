"""Peer-set sufficiency gate (WS2).

An initiation report must carry a peer-multiples table with at least two
peers; shipping a single-row peer table is the kind of defect the May 2026
sell-side review flagged on the CRM and NVDA reports. The gate runs after
the manifest is built but before any section generation.

The runner inspects the manifest's `get_fundamentals_data/*` entries (count
- 1 for the subject) and raises `InsufficientPeerSetError` when fewer than
two peers are resolvable. Setting `peer_set_override=True` on the runner
downgrades the error to a logged warning."""

from __future__ import annotations

from openlia.llm.runtime.report_v2.types import ManifestEntry

_FUNDAMENTALS_PREFIX = "get_fundamentals_data/"


class InsufficientPeerSetError(Exception):
    """Raised when the manifest packer cannot resolve at least two peers for
    a stock-initiation run.

    Carries `peer_count` (the number of peer fundamentals entries actually
    present, excluding the subject) so the caller can render an actionable
    message."""

    def __init__(self, peer_count: int, minimum: int = 2) -> None:
        self.peer_count = peer_count
        self.minimum = minimum
        super().__init__(
            f"insufficient peer set: found {peer_count} peer fundamentals "
            f"entries, need at least {minimum}"
        )


def count_peer_fundamentals(manifest_entries: list[ManifestEntry], *, subject_ticker: str) -> int:
    """Return the number of peer fundamentals entries in the manifest.

    Counts every `get_fundamentals_data/<TICKER>` identifier whose ticker
    portion differs from `subject_ticker` (case-insensitive). Both the
    manifest identifier suffix and `subject_ticker` are normalised by
    stripping any `.<EXCHANGE>` suffix (mirroring `PayloadView`'s logic),
    so "NET.US" and "NET" compare equal."""
    wanted = subject_ticker.split(".", 1)[0].upper()
    count = 0
    for entry in manifest_entries:
        ident = entry.identifier
        if not ident.startswith(_FUNDAMENTALS_PREFIX):
            continue
        suffix = ident[len(_FUNDAMENTALS_PREFIX) :]
        ticker = suffix.split(".", 1)[0].upper()
        if ticker == wanted:
            continue
        count += 1
    return count
