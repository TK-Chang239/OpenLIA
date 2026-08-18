"""write_section must promote inline chart markers to their own paragraph
(audit minor: "...is shown in {{chart:x}}." left dangling fragments and an
orphan period once renderers swapped the marker for a figure block)."""

from __future__ import annotations

from openlia.llm.runtime.report_v3.tools.output_tools import _normalize_chart_placement


def test_inline_marker_promoted_and_sentence_closed() -> None:
    md = "The trajectory is shown in {{chart:rev_fcf}}. Next sentence."
    out = _normalize_chart_placement(md)
    lines = [ln for ln in out.split("\n") if ln.strip()]
    assert "{{chart:rev_fcf}}" in lines
    idx = lines.index("{{chart:rev_fcf}}")
    assert lines[idx - 1].endswith(":")
    assert "." not in lines[idx]
    assert lines[idx + 1].startswith("Next sentence")


def test_standalone_marker_untouched() -> None:
    md = "Intro paragraph.\n\n{{chart:trend}}\n\nOutro."
    out = _normalize_chart_placement(md)
    assert "\n\n{{chart:trend}}\n\n" in out
    assert out.count("{{chart:trend}}") == 1
    # The preceding sentence already ends with a period — no colon added.
    assert "Intro paragraph.\n" in out


def test_no_markers_is_identity() -> None:
    md = "Just prose with no charts."
    assert _normalize_chart_placement(md) == md


def test_heading_before_marker_not_given_colon() -> None:
    md = "## Financial Profile\n\n{{chart:x}}\n\nBody."
    out = _normalize_chart_placement(md)
    assert "## Financial Profile\n" in out
    assert "## Financial Profile:" not in out
