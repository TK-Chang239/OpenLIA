"""Tests for Stage 7 Drafter and topological_order (Task P6)."""

from __future__ import annotations

from unittest.mock import Mock

from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import (
    SectionDrafter,
    topological_order,
)
from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import TriggerResult
from openlia.llm.runtime.report_v2.schemas.research_pool import ResearchPool

# ---------------------------------------------------------------------------
# topological_order
# ---------------------------------------------------------------------------


def test_topological_order_basic():
    dag = {"a": [], "b": ["a"], "c": ["b"]}
    result = topological_order(dag)
    assert result == ["a", "b", "c"]


def test_topological_order_includes_nodes_only_as_predecessor():
    dag = {"b": ["a"]}
    result = topological_order(dag)
    assert result.index("a") < result.index("b")
    assert set(result) == {"a", "b"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_section(
    sid: str, name: str, directive: str, depends_on: list[str], trigger_when: str | None = None
):
    s = Mock()
    s.id = sid
    s.name = name
    s.directive = directive
    s.depends_on = depends_on
    s.trigger_when = trigger_when
    return s


def _fake_research_pool() -> ResearchPool:
    return ResearchPool(
        findings_by_strand={"macro": "GDP grew 2.5%", "company": "Revenue up 10%"},
        citations=[],
    )


# ---------------------------------------------------------------------------
# SectionDrafter tests
# ---------------------------------------------------------------------------


def test_drafter_drafts_section_when_no_trigger_when():
    fake_llm = Mock()
    fake_llm.call.return_value = {"blocks": [{"type": "paragraph", "text": "Hello"}]}
    fake_evaluator = Mock()

    sections = [_make_section("intro", "Introduction", "Write intro", [])]
    dag = {"intro": []}

    drafter = SectionDrafter(llm=fake_llm, trigger_evaluator=fake_evaluator)
    outputs = drafter.draft_all(
        sections=sections,
        dag=dag,
        composer_inputs={"ticker": "AAPL"},
        research_pool=_fake_research_pool(),
        model_artifacts=[],
    )

    assert len(outputs) == 1
    out = outputs[0]
    assert out.section_id == "intro"
    assert out.status == "OK"
    assert out.blocks == [{"type": "paragraph", "text": "Hello"}]
    # evaluator should NOT be called when trigger_when is None
    fake_evaluator.evaluate.assert_not_called()


def test_drafter_skips_section_when_trigger_fires_false():
    fake_llm = Mock()
    fake_evaluator = Mock()
    fake_evaluator.evaluate.return_value = TriggerResult(fire=False, reason="no macro data")

    sections = [
        _make_section(
            "macro_section", "Macro", "Write macro", [], trigger_when="macro strand available"
        ),
    ]
    dag = {"macro_section": []}

    drafter = SectionDrafter(llm=fake_llm, trigger_evaluator=fake_evaluator)
    outputs = drafter.draft_all(
        sections=sections,
        dag=dag,
        composer_inputs={},
        research_pool=_fake_research_pool(),
        model_artifacts=[],
    )

    assert len(outputs) == 1
    out = outputs[0]
    assert out.status == "SKIPPED"
    assert out.skip_reason == "no macro data"
    # LLM drafter must NOT be called
    fake_llm.call.assert_not_called()


def test_drafter_drafts_section_when_trigger_fires_true():
    fake_llm = Mock()
    fake_llm.call.return_value = {"blocks": [{"type": "paragraph", "text": "Macro content"}]}
    fake_evaluator = Mock()
    fake_evaluator.evaluate.return_value = TriggerResult(fire=True, reason="macro data present")

    sections = [
        _make_section(
            "macro_section", "Macro", "Write macro", [], trigger_when="macro strand available"
        ),
    ]
    dag = {"macro_section": []}

    drafter = SectionDrafter(llm=fake_llm, trigger_evaluator=fake_evaluator)
    outputs = drafter.draft_all(
        sections=sections,
        dag=dag,
        composer_inputs={},
        research_pool=_fake_research_pool(),
        model_artifacts=[],
    )

    assert len(outputs) == 1
    out = outputs[0]
    assert out.status == "OK"
    fake_llm.call.assert_called_once()


def test_drafter_degraded_on_llm_error():
    fake_llm = Mock()
    fake_llm.call.side_effect = RuntimeError("LLM timeout")
    fake_evaluator = Mock()

    sections = [_make_section("body", "Body", "Write body", [])]
    dag = {"body": []}

    drafter = SectionDrafter(llm=fake_llm, trigger_evaluator=fake_evaluator)
    outputs = drafter.draft_all(
        sections=sections,
        dag=dag,
        composer_inputs={},
        research_pool=_fake_research_pool(),
        model_artifacts=[],
    )

    assert len(outputs) == 1
    out = outputs[0]
    assert out.status == "DEGRADED"
    assert "LLM timeout" in out.degraded_reason


def test_redraft_with_feedback_returns_new_blocks():
    fake_llm = Mock()
    new_blocks = [{"type": "paragraph", "text": "Revised content"}]
    fake_llm.call.return_value = {"blocks": new_blocks}
    fake_evaluator = Mock()

    drafter = SectionDrafter(llm=fake_llm, trigger_evaluator=fake_evaluator)

    blocker1 = Mock()
    blocker1.model_dump = lambda: {"issue_type": "tombstone", "severity": "blocker"}
    blocker2 = Mock()
    blocker2.model_dump = lambda: {"issue_type": "block_shape", "severity": "blocker"}

    retry_context = {"section_id": "intro", "attempt": 2}
    result = drafter.redraft_with_feedback(
        section_id="intro",
        blockers=[blocker1, blocker2],
        retry_context=retry_context,
    )

    fake_llm.call.assert_called_once()
    assert result == new_blocks
