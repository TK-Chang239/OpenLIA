"""Built-in NewsAPI.ai template tests."""

from __future__ import annotations

from openlia.connectors.builtins.newsapi_ai import NEWSAPI_AI_TEMPLATE
from openlia.connectors.builtins.types import PythonLibRecipe
from openlia.connectors.types import Category


def test_newsapi_ai_template_id_and_category() -> None:
    assert NEWSAPI_AI_TEMPLATE.template_id == "newsapi_ai"
    assert NEWSAPI_AI_TEMPLATE.category == Category.NEWS
    assert NEWSAPI_AI_TEMPLATE.api_key_env_var == "NEWSAPI_AI_API_KEY"


def test_newsapi_ai_python_lib_targets_event_registry_wrapper() -> None:
    """We instantiate EventRegistryWrapper (subclass of EventRegistry) so
    the python_lib transport can call kwargs-only methods. The native
    `EventRegistry.execQuery(query)` takes a constructed Query object,
    not kwargs, so it isn't directly callable from the transport.
    """
    modes = NEWSAPI_AI_TEMPLATE.available_modes
    assert len(modes) == 1
    py = modes[0]
    assert isinstance(py, PythonLibRecipe)
    assert py.pip_name == "eventregistry"
    assert py.import_module == "openlia.data.eventregistry_wrapper"
    assert py.instance_factory_cls == "EventRegistryWrapper"
    args = dict(py.instance_factory_args)
    assert args.get("apiKey") == "$NEWSAPI_AI_API_KEY"


def test_newsapi_ai_has_no_runner_specs() -> None:
    """All previous MR runner specs were removed — NewsAPI.ai is now
    chat-toolbox only.
    """
    assert NEWSAPI_AI_TEMPLATE.runner_specs == ()


def test_newsapi_ai_canary_tool_is_geopolitical_news() -> None:
    assert NEWSAPI_AI_TEMPLATE.canary_tool == "geopolitical_news"
