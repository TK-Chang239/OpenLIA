"""Built-in Mediastack template tests."""

from __future__ import annotations

from openlia.connectors.builtins.mediastack import MEDIASTACK_TEMPLATE
from openlia.connectors.builtins.types import PythonLibRecipe
from openlia.connectors.types import Category


def test_mediastack_template_id_and_category() -> None:
    assert MEDIASTACK_TEMPLATE.template_id == "mediastack"
    assert MEDIASTACK_TEMPLATE.category == Category.NEWS
    assert MEDIASTACK_TEMPLATE.api_key_env_var == "MEDIASTACK_API_KEY"


def test_mediastack_has_python_lib_only() -> None:
    assert len(MEDIASTACK_TEMPLATE.available_modes) == 1
    assert isinstance(MEDIASTACK_TEMPLATE.available_modes[0], PythonLibRecipe)


def test_mediastack_covers_geopolitical_news() -> None:
    need_ids = {spec.need_id for spec in MEDIASTACK_TEMPLATE.runner_specs}
    assert "geopolitical_news" in need_ids


def test_mediastack_canary_tool_set() -> None:
    assert MEDIASTACK_TEMPLATE.canary_tool is not None
