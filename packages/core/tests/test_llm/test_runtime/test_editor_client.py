from __future__ import annotations

import pytest
from _fakes import FakeProvider, FakeProviderScript
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME, EditorClient, EditorRequest
from openlia.llm.runtime.section_draft import OpenQuestion, SectionDraft
from openlia.llm.types import ToolCall


def _draft(section_id: str, content: str) -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": section_id,
            "blocks": [{"type": "text", "content": content}],
            "citations_used": ["c1"],
            "word_count": len(content.split()),
            "open_questions": [],
        }
    )


def _final_payload(title: str = "MSFT") -> dict:
    return {
        "cover": {"title": title, "subtitle": "Initiation", "tagline": "Constructive"},
        "sections": [
            {
                "id": "company_overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Overview body."}],
            }
        ],
    }


def _request() -> EditorRequest:
    return EditorRequest(
        role_prompt="ROLE",
        style_guide="STYLE",
        schema_strictness="STRICT",
        company_thesis="MSFT.",
        cross_section_themes=["t1", "t2"],
        section_drafts=[_draft("company_overview", "Overview body.")],
        open_questions=[OpenQuestion(section_id="x", question="q")],
        framework_cover_instructions="Cover fields: title, subtitle, tagline.",
    )


@pytest.mark.asyncio
async def test_editor_returns_final_payload_via_submit_report() -> None:
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=_final_payload())],
                )
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    payload = await client.compose(_request())
    assert payload["cover"]["title"] == "MSFT"
    assert payload["sections"][0]["id"] == "company_overview"


@pytest.mark.asyncio
async def test_editor_repairs_once_on_validation_failure() -> None:
    # missing tagline + empty sections
    bad = {"cover": {"title": "x", "subtitle": "y"}, "sections": []}
    good = _final_payload()
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [ToolCall(id="e1", name=EDITOR_TOOL_NAME, arguments=good)]),
            ]
        )
    )
    client = EditorClient(provider=provider, repair_budget=1, max_output_tokens=8192)
    payload = await client.compose(_request())
    assert payload["cover"]["title"] == "MSFT"
    assert len(provider.captured_requests) == 2
