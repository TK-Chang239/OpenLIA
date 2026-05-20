"""Pre-section scanners (WS3).

Part B (material-events gate) lives here. Part A (fresh-catalyst pack) will
join in a later PR sharing the same news/EDGAR/web fetch surface."""

from openlia.llm.runtime.report_v2.scanners.material_events import (
    MaterialEvent,
    MaterialEventError,
    MaterialEventScanner,
    scan_manifest,
)

__all__ = [
    "MaterialEvent",
    "MaterialEventError",
    "MaterialEventScanner",
    "scan_manifest",
]
