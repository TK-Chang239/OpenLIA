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


def test_newsapi_ai_runner_spec_targets_geopolitical_news_method() -> None:
    specs = NEWSAPI_AI_TEMPLATE.runner_specs
    assert len(specs) == 1
    spec = specs[0]
    assert spec.need_id == "geopolitical_news"
    assert spec.access_mode == "python_lib"
    assert spec.module == "openlia.data.eventregistry_wrapper"
    assert spec.method == "EventRegistryWrapper.geopolitical_news"
    # Bindings match the runtime parameters declared in macro_research.needs.yaml
    assert set(spec.param_bindings.keys()) == {"window_days", "limit"}
    assert spec.param_bindings["window_days"].to_arg == "window_days"
    assert spec.param_bindings["limit"].to_arg == "limit"


def test_newsapi_ai_canary_tool_is_geopolitical_news() -> None:
    assert NEWSAPI_AI_TEMPLATE.canary_tool == "geopolitical_news"
