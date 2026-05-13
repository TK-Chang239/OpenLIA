"""Phase 6 — ChatRunner consumes attachments.

Verifies that the previously dead ``attachments`` parameter on
``ChatRunner.run()`` now wires the materializer in and that the resulting
content blocks are attached to the last user message in the LLMRequest sent
to the provider.

These tests exercise the public surface — call ``run()`` with attachments,
inspect the provider's ``captured_requests`` for the materialized blocks.
Internal carrier shape (``Message.content_blocks``) is verified through
its observable effect, not asserted as a schema invariant.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.messages import (
    Attachment,
    ChatMessage,
    ImageBlock,
    TextBlock,
)
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

pytestmark = pytest.mark.asyncio


def _empty_skill_registry(root: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=root)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    root.mkdir()
    (root / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: You are the Secretary.
            """
        )
    )
    return root


def _resolved(*, vision: bool = True, pdf_native: bool = True) -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=False,  # no tools so the runner falls through to streaming
            structured_output=True,
            vision=vision,
            pdf_native=pdf_native,
            max_context_tokens=200_000,
        ),
        overrides={},
    )


class _Registry:
    pass


def _always_resolved(*, resolved: ResolvedModel):
    def _resolve(**_):
        return resolved

    return _resolve


def _make_runner(prompts_root: Path, provider: FakeProvider) -> ChatRunner:
    data = FakeDataDispatcher(manifest={"secretary": {}})
    return ChatRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always_resolved(resolved=_resolved()),
        registry=_Registry(),
        provider_factory=lambda resolved: provider,
        skill_registry=_empty_skill_registry(prompts_root / "_skills"),
        message_id_factory=lambda: "m_1",
    )


async def _drain(events) -> None:
    async for _ in events:
        pass


# ─── Tracer bullet ───────────────────────────────────────────────────────────


async def test_attachments_materialize_into_user_message_blocks(
    prompts_root: Path, tmp_path: Path
) -> None:
    """A text attachment must appear as a TextBlock alongside the user's
    typed message in the LLMRequest the provider receives."""
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    runner = _make_runner(prompts_root, provider)

    txt_path = tmp_path / "notes.txt"
    txt_path.write_bytes(b"important context")
    att = Attachment(
        id="att-1",
        filename="notes.txt",
        mime_type="text/plain",
        storage_path=str(txt_path),
        size_bytes=17,
    )

    await _drain(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="please read")],
            attachments=[att],
        )
    )

    assert provider.captured_requests, "provider should have received a request"
    request = provider.captured_requests[-1]
    user_msg = next(m for m in reversed(request.messages) if m.role == "user")
    blocks = list(user_msg.content_blocks)
    text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
    assert any(
        b.source_filename == "notes.txt" and b.text == "important context" for b in text_blocks
    )


async def test_no_attachments_means_no_content_blocks(
    prompts_root: Path,
) -> None:
    """The ``attachments`` parameter remains optional — omitting it preserves
    the v1 behavior where messages have no content_blocks."""
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    runner = _make_runner(prompts_root, provider)

    await _drain(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    request = provider.captured_requests[-1]
    user_msg = next(m for m in reversed(request.messages) if m.role == "user")
    assert tuple(user_msg.content_blocks) == ()


async def test_image_attachment_routes_through_to_provider_when_model_supports_vision(
    prompts_root: Path, tmp_path: Path
) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    runner = _make_runner(prompts_root, provider)

    img_path = tmp_path / "screen.png"
    img_path.write_bytes(b"\x89PNG fake bytes")
    att = Attachment(
        id="att-img",
        filename="screen.png",
        mime_type="image/png",
        storage_path=str(img_path),
        size_bytes=15,
    )

    await _drain(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[ChatMessage(role="user", content="what's in this?")],
            attachments=[att],
        )
    )

    request = provider.captured_requests[-1]
    user_msg = next(m for m in reversed(request.messages) if m.role == "user")
    image_blocks = [b for b in user_msg.content_blocks if isinstance(b, ImageBlock)]
    assert len(image_blocks) == 1
    assert image_blocks[0].source_filename == "screen.png"
    assert image_blocks[0].mime_type == "image/png"


async def test_attachments_only_attach_to_the_last_user_message(
    prompts_root: Path, tmp_path: Path
) -> None:
    """In a multi-turn conversation, attachments belong to the *current* user
    turn — earlier user messages must remain block-free."""
    provider = FakeProvider(script=FakeProviderScript(turns=[("final", ""), ("tokens", ["ok"])]))
    runner = _make_runner(prompts_root, provider)

    txt_path = tmp_path / "now.txt"
    txt_path.write_bytes(b"current attachment")
    att = Attachment(
        id="att-now",
        filename="now.txt",
        mime_type="text/plain",
        storage_path=str(txt_path),
        size_bytes=18,
    )

    await _drain(
        runner.run(
            department_id="secretary",
            user_id="u_1",
            messages=[
                ChatMessage(role="user", content="earlier turn"),
                ChatMessage(role="assistant", content="reply"),
                ChatMessage(role="user", content="new turn"),
            ],
            attachments=[att],
        )
    )

    request = provider.captured_requests[-1]
    user_msgs = [m for m in request.messages if m.role == "user"]
    assert len(user_msgs) == 2
    assert tuple(user_msgs[0].content_blocks) == ()
    assert any(
        getattr(b, "source_filename", None) == "now.txt" for b in user_msgs[-1].content_blocks
    )
