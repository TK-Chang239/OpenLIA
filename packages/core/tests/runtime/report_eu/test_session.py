from openlia.llm.runtime.report_eu.session import LLMSession


def test_create_allows_model_without_native_web_search():
    # A model lacking web_search_native must NOT raise for EU v2.
    session = LLMSession.create(
        provider_kind="ollama",
        model="llama3.1",
        capability_override={"web_search_native": False, "max_output_tokens": 4096},
    )
    assert session.provider_kind == "ollama"
    assert session.capabilities.web_search_native is False
