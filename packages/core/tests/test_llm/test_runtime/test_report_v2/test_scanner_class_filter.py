"""Tests for the PR 6 lift: scanners accept an explicit event-class filter.

`scan_manifest` and `scan_catalysts` now take an optional `event_classes`
parameter that restricts which event classes the scanner inspects. When None,
all built-in classes apply (legacy behavior). The default `stock_initiation`
template declares the full set of classes for both scanners; future custom
templates can opt out of classes they don't care about.
"""

from __future__ import annotations


def test_default_template_declares_all_material_event_classes() -> None:
    from openlia.llm.runtime.report_v2.scanners.material_events import ALL_MATERIAL_EVENT_CLASSES
    from openlia.reports.frameworks.loaders.stock_initiation import (
        load_stock_initiation_template,
    )

    spec = load_stock_initiation_template()

    assert set(spec.material_event_classes) == ALL_MATERIAL_EVENT_CLASSES


def test_default_template_declares_all_catalyst_classes() -> None:
    from openlia.llm.runtime.report_v2.scanners.catalyst_pack import ALL_CATALYST_CLASSES
    from openlia.reports.frameworks.loaders.stock_initiation import (
        load_stock_initiation_template,
    )

    spec = load_stock_initiation_template()

    assert set(spec.catalyst_classes) == ALL_CATALYST_CLASSES


def test_scan_manifest_with_empty_event_classes_returns_nothing() -> None:
    from openlia.llm.runtime.report_v2.scanners import scan_manifest

    events = scan_manifest(
        manifest=[],
        subject_ticker="X",
        event_classes=frozenset(),
    )

    assert events == []


def test_scan_catalysts_with_empty_event_classes_returns_nothing() -> None:
    from openlia.llm.runtime.report_v2.scanners import scan_catalysts

    events = scan_catalysts(
        manifest_entries=[],
        subject_ticker="X",
        event_classes=frozenset(),
    )

    assert events == []


def test_all_material_event_classes_matches_pattern_set() -> None:
    from openlia.llm.runtime.report_v2.scanners.material_events import (
        _PATTERNS,
        ALL_MATERIAL_EVENT_CLASSES,
    )

    assert set(_PATTERNS.keys()) == ALL_MATERIAL_EVENT_CLASSES


def test_all_catalyst_classes_matches_pattern_set() -> None:
    from openlia.llm.runtime.report_v2.scanners.catalyst_pack import (
        _PATTERNS,
        ALL_CATALYST_CLASSES,
    )

    assert set(_PATTERNS.keys()) == ALL_CATALYST_CLASSES
