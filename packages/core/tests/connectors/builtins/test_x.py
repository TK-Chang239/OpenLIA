"""Built-in X template tests."""

from __future__ import annotations

from openlia.connectors.builtins.types import PythonLibRecipe
from openlia.connectors.builtins.x import X_TEMPLATE
from openlia.connectors.types import Category


def test_x_template_id_and_category() -> None:
    assert X_TEMPLATE.template_id == "x"
    assert X_TEMPLATE.category == Category.SOCIAL
    # Bearer token, not a generic API key — X uses Bearer auth.
    assert X_TEMPLATE.api_key_env_var == "X_API_BEARER_TOKEN"


def test_x_has_no_runner_specs() -> None:
    """X is chat-only on day 1; no runner-need mappings."""
    assert X_TEMPLATE.runner_specs == ()


def test_x_python_lib_targets_x_wrapper() -> None:
    """We instantiate XClient (subclass of xdk.Client) so the python_lib
    transport sees flat methods. xdk.Client groups its API under nested
    resources (client.posts.<method>), which the transport's
    list_tools walker can't discover.
    """
    modes = X_TEMPLATE.available_modes
    assert len(modes) == 1
    py = modes[0]
    assert isinstance(py, PythonLibRecipe)
    assert py.pip_name == "xdk"
    assert py.import_module == "openlia.data.x_wrapper"
    assert py.instance_factory_cls == "XClient"
    args = dict(py.instance_factory_args)
    assert args.get("bearer_token") == "$X_API_BEARER_TOKEN"


def test_x_canary_tool_is_search_recent_posts() -> None:
    """search_recent_posts is the cheapest live call — good canary signal."""
    assert X_TEMPLATE.canary_tool == "search_recent_posts"
