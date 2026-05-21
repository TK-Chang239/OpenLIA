"""Tests for TriggerEvaluator (Task P6)."""

from __future__ import annotations

from unittest.mock import Mock

from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import (
    TriggerEvaluator,
    TriggerResult,
)


def _make_evaluator(llm_return: dict) -> tuple[TriggerEvaluator, Mock]:
    fake_llm = Mock()
    fake_llm.call.return_value = llm_return
    return TriggerEvaluator(llm=fake_llm), fake_llm


def test_trigger_fires_true_when_llm_returns_true():
    evaluator, _ = _make_evaluator({"fire": True, "reason": "condition met"})
    result = evaluator.evaluate(
        condition="some condition",
        composer_inputs={"ticker": "AAPL"},
        deps_markdown={"intro": "# Intro"},
        research_pool_index={"strand1": "findings prefix"},
        model_artifacts_index={"art1": "chart description"},
    )
    assert isinstance(result, TriggerResult)
    assert result.fire is True
    assert result.reason == "condition met"


def test_trigger_fires_false_when_llm_returns_false():
    evaluator, _ = _make_evaluator({"fire": False, "reason": "condition not met"})
    result = evaluator.evaluate(
        condition="some condition",
        composer_inputs={"ticker": "AAPL"},
        deps_markdown={},
        research_pool_index={},
        model_artifacts_index={},
    )
    assert result.fire is False
    assert result.reason == "condition not met"


def test_trigger_evaluator_fails_open_on_error():
    fake_llm = Mock()
    fake_llm.call.side_effect = RuntimeError("network timeout")
    evaluator = TriggerEvaluator(llm=fake_llm)
    result = evaluator.evaluate(
        condition="some condition",
        composer_inputs={},
        deps_markdown={},
        research_pool_index={},
        model_artifacts_index={},
    )
    assert result.fire is True
    assert result.reason.startswith("evaluator_failed:")


def test_trigger_passes_all_context_to_llm():
    evaluator, fake_llm = _make_evaluator({"fire": True, "reason": "ok"})
    composer_inputs = {"ticker": "MSFT", "horizon": "1y"}
    deps_markdown = {"intro": "**Intro**"}
    research_pool_index = {"macro": "GDP grew 2%..."}
    model_artifacts_index = {"dcf_chart": "DCF valuation chart"}

    evaluator.evaluate(
        condition="check macro strand",
        composer_inputs=composer_inputs,
        deps_markdown=deps_markdown,
        research_pool_index=research_pool_index,
        model_artifacts_index=model_artifacts_index,
    )

    fake_llm.call.assert_called_once()
    _call_kwargs = fake_llm.call.call_args
    # call may be positional or keyword
    if _call_kwargs.kwargs:
        fallback = _call_kwargs.args[1] if len(_call_kwargs.args) > 1 else None
        user_dict = _call_kwargs.kwargs.get("user", fallback)
    else:
        user_dict = _call_kwargs.args[1] if len(_call_kwargs.args) > 1 else None

    assert user_dict is not None
    assert "composer_inputs" in user_dict
    assert "deps_markdown" in user_dict
    assert "research_pool_index" in user_dict
    assert "model_artifacts_index" in user_dict
