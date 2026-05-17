from __future__ import annotations

import pytest
from _fakes import FakeProvider, FakeProviderScript
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME, EditorClient, EditorRequest
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.types import ToolCall


def _final_payload() -> dict:
    return {
        "cover": {"title": "x", "subtitle": "y", "tagline": "z"},
        "sections": [
            {
                "id": "company_overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Final body."}],
            }
        ],
    }


def _draft() -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": [{"type": "text", "content": "Body."}],
            "citations_used": [],
            "word_count": 1,
            "open_questions": [],
        }
    )


def _base_request(revision_brief: str | None = None) -> EditorRequest:
    return EditorRequest(
        role_prompt="ROLE",
        style_guide="STYLE",
        schema_strictness="STRICT",
        company_thesis="t",
        cross_section_themes=["t1", "t2"],
        section_drafts=[_draft()],
        open_questions=[],
        framework_cover_instructions="cover instructions",
        revision_brief=revision_brief,
        sections_to_focus=None,
        chat_transcript_excerpt=None,
    )


@pytest.mark.asyncio
async def test_editor_request_accepts_revision_fields() -> None:
    req = _base_request(revision_brief="Fix the Q4 capex number")
    assert req.revision_brief == "Fix the Q4 capex number"
    assert req.sections_to_focus is None
    assert req.chat_transcript_excerpt is None


@pytest.mark.asyncio
async def test_compose_uses_revision_role_prompt_when_brief_set() -> None:
    """When revision_brief is set, EditorClient must build its system
    prompt from revision_editor_role.yaml.j2 (loaded by caller and
    passed via role_prompt) — meaning the role_prompt string itself
    should be the revision role text."""
    # Caller injects revision_role_prompt content via role_prompt.
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())],
                ),
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    req = _base_request(revision_brief="Tighten the risk section")
    req = req.model_copy(update={"role_prompt": "REVISION_ROLE_PROMPT"})
    payload = await client.compose(req)
    assert payload["cover"]["title"] == "x"
    # Verify the system prompt sent to the provider includes the revision role.
    req_sent = provider.captured_requests[0]
    assert "REVISION_ROLE_PROMPT" in req_sent.system


@pytest.mark.asyncio
async def test_compose_passes_revision_brief_into_user_prompt() -> None:
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())],
                ),
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    req = _base_request(revision_brief="MUST_APPEAR_IN_USER_PROMPT")
    await client.compose(req)
    user_msg = next(m for m in provider.captured_requests[0].messages if m.role == "user")
    assert "MUST_APPEAR_IN_USER_PROMPT" in user_msg.content


@pytest.mark.asyncio
async def test_compose_includes_chat_transcript_excerpt_when_set() -> None:
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())],
                ),
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    req = _base_request(revision_brief="x")
    req = req.model_copy(update={"chat_transcript_excerpt": "USER_SAID_X"})
    await client.compose(req)
    user_msg = next(m for m in provider.captured_requests[0].messages if m.role == "user")
    assert "USER_SAID_X" in user_msg.content
