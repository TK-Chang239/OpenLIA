from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from _fakes import FakeProvider, FakeProviderScript
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
from openlia.llm.runtime.events import ReportComplete, ReportPhase
from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report_context_bundle import (
    ReportContextBundle,
    persist_bundle,
)
from openlia.llm.runtime.revision_runner import RevisionRunner
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192
        ),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
    (root / "shared" / "revision_editor_role.yaml.j2").write_text("REVISION_ROLE")
    (root / "shared" / "report_schema_strictness.yaml.j2").write_text("STRICT")
    return root


@pytest.fixture
def bundle_dir(tmp_path: Path) -> Path:
    return tmp_path / "bundles"


@pytest.fixture
def seeded_source_bundle(tmp_path: Path, bundle_dir: Path) -> str:
    bundle_dir.mkdir()
    plan = ReportPlan.model_validate(
        {
            "company_thesis": "thesis",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                {
                    "section_id": "company_overview",
                    "title": "Overview",
                    "narrative_goal": "g",
                    "key_questions": ["q1", "q2", "q3"],
                    "target_depth": "standard",
                    "word_budget": 200,
                    "data_paths": [],
                    "cross_refs": [],
                }
            ],
        }
    )
    draft = SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": [{"type": "text", "content": "Original body."}],
            "citations_used": [],
            "word_count": 2,
            "open_questions": [],
        }
    )
    persist_bundle(
        ReportContextBundle(
            plan=plan,
            fetched_data={},
            section_drafts=[draft],
            payload_refs={},
            generation_meta={},
        ),
        path=bundle_dir / "r_source.json.gz",
    )
    return "r_source"


@pytest.fixture
def seeded_source_report(db_session_factory, test_user, seeded_source_bundle) -> str:
    from openlia_server.db.models.content import Report

    source_schema = {
        "schema_version": "2.0",
        "department": "equity_research",
        "generated_at": "2026-05-17T00:00:00+00:00",
        "cover": {"title": "MSFT", "subtitle": "Init", "tagline": "Constructive"},
        "sections": [
            {
                "id": "company_overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Original body."}],
            }
        ],
    }
    with db_session_factory() as session:
        row = Report(
            id=seeded_source_bundle,
            user_id=test_user.id,
            department="equity_research",
            report_type="stock_initiation",
            title="MSFT",
            content_markdown="Original body.",
            content_structured=source_schema,
            model_ref="fake-1",
        )
        session.add(row)
        session.commit()
    return seeded_source_bundle


@pytest.fixture
def seeded_chat_with_messages(db_session_factory, test_user, seeded_source_report) -> str:
    from openlia_server.db.models.content import ChatMessage, ChatSession

    with db_session_factory() as session:
        chat = ChatSession(
            id="sess_test",
            user_id=test_user.id,
            department="equity_research",
            attached_report_id=seeded_source_report,
        )
        session.add(chat)
        session.add(
            ChatMessage(
                id=str(uuid.uuid4()),
                session_id="sess_test",
                role="user",
                content="Q4 capex is wrong; should be $14B",
            )
        )
        session.add(
            ChatMessage(
                id=str(uuid.uuid4()),
                session_id="sess_test",
                role="assistant",
                content="You're right; using $14B",
            )
        )
        session.commit()
    return "sess_test"


def _editor_args() -> dict:
    return {
        "cover": {"title": "MSFT (revised)", "subtitle": "Init", "tagline": "Constructive"},
        "sections": [
            {
                "id": "company_overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Revised body."}],
            }
        ],
    }


@pytest.mark.asyncio
async def test_revision_runner_happy_path(
    prompts_root: Path,
    bundle_dir: Path,
    seeded_source_report: str,
    seeded_chat_with_messages: str,
    db_session_factory,
) -> None:
    flagship = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())],
                ),
            ]
        )
    )
    runner = RevisionRunner(
        prompts=PromptLoader(root=prompts_root),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: flagship,
        report_id_factory=lambda: "r_revised",
        bundle_dir=bundle_dir,
        db_session_factory=db_session_factory,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        source_report_id=seeded_source_report,
        chat_session_id=seeded_chat_with_messages,
        revision_brief="Fix Q4 capex per discussion",
        sections_to_focus=None,
    ):
        events.append(ev)

    types = [type(e).__name__ for e in events]
    assert "ReportStart" in types
    assert "ReportComplete" in types
    phases = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert "loading_context" in phases
    assert "editing" in phases
    assert "finalizing" in phases
    final = [e for e in events if isinstance(e, ReportComplete)][-1]
    assert final.schema["cover"]["title"] == "MSFT (revised)"
    assert final.schema["department"] == "equity_research"
