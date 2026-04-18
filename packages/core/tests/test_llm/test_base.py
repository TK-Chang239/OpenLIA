from __future__ import annotations

import pytest

from openlia.llm.base import LLMProvider
from openlia.llm.types import Capabilities, ProviderCredentials


class _Concrete(LLMProvider):
    kind = "openai"

    async def list_models(self):
        return []

    async def generate(self, request):
        raise NotImplementedError

    async def stream(self, request):
        raise NotImplementedError
        yield

    async def test_connection(self, model):
        raise NotImplementedError


def test_cannot_instantiate_abstract_base() -> None:
    with pytest.raises(TypeError):
        LLMProvider(  # type: ignore[abstract]
            credentials=ProviderCredentials(api_key="k", base_url=None),
            model="m",
            capabilities=Capabilities(),
        )


def test_concrete_subclass_stores_fields() -> None:
    creds = ProviderCredentials(api_key="sk-x", base_url=None)
    caps = Capabilities()
    a = _Concrete(credentials=creds, model="gpt-5.4", capabilities=caps)
    assert a.credentials is creds
    assert a.model == "gpt-5.4"
    assert a.capabilities is caps
    assert a.kind == "openai"


def test_status_to_exception_auth() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import AuthError

    with pytest.raises(AuthError):
        status_to_exception(status_code=401, body_text="invalid key")


def test_status_to_exception_rate_limit_with_retry_after() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import RateLimitError

    with pytest.raises(RateLimitError) as excinfo:
        status_to_exception(status_code=429, body_text="slow", headers={"retry-after": "17"})
    assert excinfo.value.retry_after_seconds == 17


def test_status_to_exception_rate_limit_missing_retry_after() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import RateLimitError

    with pytest.raises(RateLimitError) as excinfo:
        status_to_exception(status_code=429, body_text="slow")
    assert excinfo.value.retry_after_seconds is None


def test_status_to_exception_outage() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import ProviderOutageError

    with pytest.raises(ProviderOutageError):
        status_to_exception(status_code=502, body_text="bad gateway")


def test_status_to_exception_model_not_found() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import ModelNotFoundError

    with pytest.raises(ModelNotFoundError):
        status_to_exception(status_code=404, body_text="model not found")


def test_status_to_exception_context_length() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import ContextLengthError

    with pytest.raises(ContextLengthError) as excinfo:
        status_to_exception(
            status_code=400,
            body_text="This model's maximum context length is 8192 tokens",
        )
    assert excinfo.value.limit == 8192


def test_status_to_exception_plain_400_is_capability_error() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import CapabilityError

    with pytest.raises(CapabilityError):
        status_to_exception(status_code=400, body_text="tool use is not supported on this model")
