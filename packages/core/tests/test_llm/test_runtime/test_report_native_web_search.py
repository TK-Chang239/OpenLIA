"""ReportRunner must forward ``native_tools=("web_search",)`` and
``web_search_max_uses`` on every ``LLMRequest`` sent during the tool
loop when the dispatcher's web search resolution is ``native``. Without
this, the provider never receives the native web_search tool block and
the model cannot invoke it — zero billable web_search calls.

These tests pin the outgoing protocol contract (LLMRequest fields the
provider sees), not internal state, so they survive refactors.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

pytestmark = pytest.mark.asyncio


def _empty_skill_registry(tmp_path: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=tmp_path)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps(
            {
                "title": "Stock Initiation",
                "sections": [
                    {"id": "overview", "title": "Overview", "instructions": "..."},
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    shared = root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("discipline.\n")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
                  Framework: {{ framework | tojson }}
            """
        )
    )
    return root


def _resolved(*, web_search_native: bool) -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=True,
            structured_output=True,
            web_search_native=web_search_native,
        ),
        overrides={},
    )


class _Registry:
    pass


def _always(resolved: ResolvedModel):
    def _r(*, department_id, user_id, registry, model_id_override=None):
        return resolved

    return _r


async def _collect(it):
    return [e async for e in it]


def _build(
    *,
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    provider: FakeProvider,
    variant: str | None,
) -> ReportRunner:
    return ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(
                available=variant is not None,
                variant=variant,
                adapter=None,
            ),
        ),
        resolve=_always(_resolved(web_search_native=variant == "native")),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path / "_skills"),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_ws",
    )


async def test_report_request_carries_native_web_search_when_variant_native(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    submit_call = ToolCall(
        id="t1",
        name="submit_report",
        arguments={
            "cover": {"title": "AAPL"},
            "sections": [{"id": "overview", "blocks": []}],
        },
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[("tool_calls", [submit_call])] * 30
        )
    )
    runner = _build(
        prompts_root=prompts_root,
        frameworks_root=frameworks_root,
        tmp_path=tmp_path,
        provider=provider,
        variant="native",
    )
    try:
        await _collect(
            runner.run(
                department_id="equity_research",
                user_id="u_1",
                request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
            )
        )
    except IndexError:
        pass
    assert provider.captured_requests
    first = provider.captured_requests[0]
    assert first.native_tools == ("web_search",), (
        f"expected native_tools=('web_search',) on first turn, got {first.native_tools!r}"
    )
    assert first.web_search_max_uses is not None


async def test_report_request_omits_native_web_search_when_variant_not_native(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    submit_call = ToolCall(
        id="t1",
        name="submit_report",
        arguments={
            "cover": {"title": "AAPL"},
            "sections": [{"id": "overview", "blocks": []}],
        },
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[("tool_calls", [submit_call])] * 30
        )
    )
    runner = _build(
        prompts_root=prompts_root,
        frameworks_root=frameworks_root,
        tmp_path=tmp_path,
        provider=provider,
        variant=None,
    )
    try:
        await _collect(
            runner.run(
                department_id="equity_research",
                user_id="u_1",
                request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
            )
        )
    except IndexError:
        pass
    assert provider.captured_requests
    first = provider.captured_requests[0]
    assert first.native_tools == ()
