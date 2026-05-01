"""Built-in X template tests."""

from __future__ import annotations

from openlia.connectors.builtins.x import X_TEMPLATE
from openlia.connectors.types import Category


def test_x_template_id_and_category() -> None:
    assert X_TEMPLATE.template_id == "x"
    assert X_TEMPLATE.category == Category.SOCIAL


def test_x_has_no_runner_specs() -> None:
    """X is chat-only on day 1; no runner-need mappings."""
    assert X_TEMPLATE.runner_specs == ()


def test_x_has_at_least_one_mode() -> None:
    assert len(X_TEMPLATE.available_modes) >= 1


def test_x_canary_tool_set() -> None:
    assert X_TEMPLATE.canary_tool is not None
