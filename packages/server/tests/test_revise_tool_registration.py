"""When OPENLIA_REVISION_PASS_ENABLED=1 and the chat session has
attached_report_id, the `revise_report` tool is present in the
context's tool list. With flag off, it's absent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.report_context_bundle import (
    ReportContextBundle,
    persist_bundle,
)
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia_server.services.report_chat_context import (
    build_chat_context_for_session,
)

# ---------------------------------------------------------------------------
# Minimal inline fake — mirrors test_report_chat_context.py pattern
# ---------------------------------------------------------------------------


@dataclass
class _FakeDataDispatcher:
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


def _stub_dispatcher() -> ToolDispatcher:
    return ToolDispatcher(
        data_dispatcher=_FakeDataDispatcher(manifest={"equity_research": {}}),
        web_search=WebSearchResolution(False, None, None),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_bundle(tmp_path: Path) -> Path:
    """Write a valid bundle at tmp_path/bundles/r_test.json.gz."""
    bundle_dir = tmp_path / "bundles"
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
    persist_bundle(bundle, path=bundle_dir / "r_test.json.gz")
    return bundle_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_revise_report_tool_present_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    seeded_bundle: Path,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    result = build_chat_context_for_session(
        attached_report_id="r_test",
        bundle_dir=seeded_bundle,
        report_is_tombstoned=False,
        dispatcher=_stub_dispatcher(),
        department_id="equity_research",
        has_web_search=True,
    )
    tool_names = {t.name for t in result.tools}
    assert "revise_report" in tool_names


def test_revise_report_tool_absent_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    seeded_bundle: Path,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    result = build_chat_context_for_session(
        attached_report_id="r_test",
        bundle_dir=seeded_bundle,
        report_is_tombstoned=False,
        dispatcher=_stub_dispatcher(),
        department_id="equity_research",
        has_web_search=True,
    )
    tool_names = {t.name for t in result.tools}
    assert "revise_report" not in tool_names
