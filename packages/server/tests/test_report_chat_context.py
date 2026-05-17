"""When a chat session has attached_report_id set, the context service:
1. Loads the ReportContextBundle from disk
2. Seeds the ToolDispatcher's payload_store with bundle.payload_refs
3. Returns a tool list that includes read_payload + the existing
   department chat tools
4. Returns a "locked" flag when the bundle is missing or the report
   is tombstoned (caller is responsible for rendering the locked UI)"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.report_context_bundle import (
    ReportContextBundle,
    persist_bundle,
)
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia_server.services.report_chat_context import (
    ChatContextResult,
    build_chat_context_for_session,
)

# ---------------------------------------------------------------------------
# Minimal inline fake — avoids cross-package sys.path hacks
# ---------------------------------------------------------------------------


@dataclass
class _FakeDataDispatcher:
    """Minimal DataProviderDispatcher implementation for test use."""

    manifest: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        return list(self.manifest.get(department_id, {}).values())

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return {"tool": tool_name, "args": arguments}

    async def expand_tools(
        self,
        *,
        department_id: str,
        reason: str,
        category_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def available_categories(self) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bundle_at(path: Path) -> ReportContextBundle:
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
            "blocks": [{"type": "text", "content": "Body."}],
            "citations_used": [],
            "word_count": 1,
            "open_questions": [],
        }
    )
    bundle = ReportContextBundle(
        plan=plan,
        fetched_data={},
        section_drafts=[draft],
        payload_refs={"r_abc_01": {"ticker": "MSFT", "price": 190.5}},
        generation_meta={},
    )
    persist_bundle(bundle, path=path)
    return bundle


def _stub_dispatcher() -> ToolDispatcher:
    return ToolDispatcher(
        data_dispatcher=_FakeDataDispatcher(manifest={"equity_research": {}}),
        web_search=WebSearchResolution(False, None, None),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_loaded_bundle_seeds_payload_store_and_registers_read_payload(
    tmp_path: Path,
) -> None:
    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    _bundle_at(bundle_dir / "r_test.json.gz")
    dispatcher = _stub_dispatcher()
    result = build_chat_context_for_session(
        attached_report_id="r_test",
        bundle_dir=bundle_dir,
        report_is_tombstoned=False,
        dispatcher=dispatcher,
        department_id="equity_research",
        has_web_search=True,
    )
    assert isinstance(result, ChatContextResult)
    assert result.locked is False
    assert "r_abc_01" in dispatcher._payload_store
    tool_names = {t.name for t in result.tools}
    assert "read_payload" in tool_names


def test_missing_bundle_returns_locked_with_message(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    dispatcher = _stub_dispatcher()
    result = build_chat_context_for_session(
        attached_report_id="r_missing",
        bundle_dir=bundle_dir,
        report_is_tombstoned=False,
        dispatcher=dispatcher,
        department_id="equity_research",
        has_web_search=True,
    )
    assert result.locked is True
    assert "can no longer be fetched" in result.lock_message.lower()


def test_tombstoned_report_returns_locked_with_message(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    _bundle_at(bundle_dir / "r_test.json.gz")  # bundle exists, but report is tombstoned
    dispatcher = _stub_dispatcher()
    result = build_chat_context_for_session(
        attached_report_id="r_test",
        bundle_dir=bundle_dir,
        report_is_tombstoned=True,
        dispatcher=dispatcher,
        department_id="equity_research",
        has_web_search=True,
    )
    assert result.locked is True
    assert "can no longer be fetched" in result.lock_message.lower()
