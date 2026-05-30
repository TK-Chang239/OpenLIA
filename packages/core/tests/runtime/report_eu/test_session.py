from openlia.llm.runtime.report_eu.session import LLMSession

from ._fakes import FakeLLMProvider, script_text


def test_create_allows_model_without_native_web_search():
    # A model lacking web_search_native must NOT raise for EU v2.
    session = LLMSession.create(
        provider_kind="ollama",
        model="llama3.1",
        capability_override={"web_search_native": False, "max_output_tokens": 4096},
    )
    assert session.provider_kind == "ollama"
    assert session.capabilities.web_search_native is False


async def test_generate_enables_conversation_caching():
    # The multi-turn engine must opt into prefix caching so prior tool
    # results are re-read from cache, not re-billed every turn.
    session = LLMSession.create(
        provider_kind="ollama",
        model="llama3.1",
        capability_override={"web_search_native": False, "max_output_tokens": 4096},
    )
    fake = FakeLLMProvider(scripted_responses=[script_text("done")])
    session.attach_adapter(fake)

    from openlia.llm.types import Message

    await session.generate(messages=[Message(role="user", content="hi")])

    assert fake.captured_requests[-1].cache_conversation is True
