from __future__ import annotations

from openlia.llm.types import (
    Capabilities,
    Capability,
    DepartmentRequirements,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ProviderCredentials,
    ResolvedModel,
    TestResult,
)


def test_capabilities_defaults_are_conservative() -> None:
    caps = Capabilities()
    assert caps.streaming is True
    assert caps.tool_calling is False
    assert caps.structured_output is False
    assert caps.vision is False
    assert caps.web_search_native is False
    assert caps.max_context_tokens == 8192
    assert caps.max_output_tokens == 2048


def test_capability_enum_values() -> None:
    assert Capability.STREAMING.value == "streaming"
    assert Capability.TOOL_CALLING.value == "tool_calling"
    assert Capability.STRUCTURED_OUTPUT.value == "structured_output"
    assert Capability.VISION.value == "vision"
    assert Capability.WEB_SEARCH.value == "web_search"


def test_message_minimal() -> None:
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_llm_request_construction() -> None:
    req = LLMRequest(
        messages=[Message(role="user", content="hi")],
        system="be nice",
        max_tokens=128,
        temperature=0.2,
    )
    assert req.messages[0].content == "hi"
    assert req.system == "be nice"
    assert req.tools is None
    assert req.response_format is None
    assert req.stop is None


def test_llm_response_shape() -> None:
    resp = LLMResponse(
        text="hello back",
        finish_reason="stop",
        input_tokens=5,
        output_tokens=3,
    )
    assert resp.text == "hello back"
    assert resp.tool_calls == []


def test_llm_chunk_shape() -> None:
    chunk = LLMChunk(delta="to", finish_reason=None)
    assert chunk.delta == "to"
    assert chunk.finish_reason is None


def test_model_info_shape() -> None:
    mi = ModelInfo(id="gpt-5.4", display_name="GPT 5.4", context_window=200_000)
    assert mi.id == "gpt-5.4"
    assert mi.context_window == 200_000


def test_provider_credentials_api_key_mode() -> None:
    creds = ProviderCredentials(api_key="sk-...", base_url=None)
    assert creds.api_key == "sk-..."
    assert creds.base_url is None


def test_provider_credentials_base_url_only() -> None:
    creds = ProviderCredentials(api_key=None, base_url="http://localhost:11434")
    assert creds.api_key is None
    assert creds.base_url == "http://localhost:11434"


def test_test_result_ok() -> None:
    tr = TestResult(ok=True, latency_ms=142, error_class=None, error_msg=None)
    assert tr.ok is True
    assert tr.latency_ms == 142


def test_test_result_failure_carries_error_class() -> None:
    tr = TestResult(ok=False, latency_ms=0, error_class="AuthError", error_msg="bad key")
    assert tr.ok is False
    assert tr.error_class == "AuthError"


def test_department_requirements_defaults() -> None:
    r = DepartmentRequirements(
        required=[Capability.STREAMING, Capability.TOOL_CALLING],
    )
    assert Capability.STREAMING in r.required
    assert r.preferred == []
    assert r.min_output_tokens == 0
    assert r.min_context_tokens == 0


def test_resolved_model_shape() -> None:
    rm = ResolvedModel(
        provider_kind="openai",
        provider_id="p1",
        model_id="m1",
        model_ref="gpt-5.4",
        credentials=ProviderCredentials(api_key="sk-...", base_url=None),
        capabilities=Capabilities(),
        overrides={"temperature": 0.3},
    )
    assert rm.model_ref == "gpt-5.4"
    assert rm.model_id == "m1"
