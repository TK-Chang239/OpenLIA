"""RevisionRunner — one editor pass producing a revised ReportSchema.

Input: source ReportSchema, source ReportContextBundle, chat transcript.
Output: a new ReportSchema yielded via ReportComplete.

Bundle inheritance: copies the source bundle file to the new report
id's path on success so the chat-followup feature works on the
revised report immediately.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.chat_transcript_compressor import compress_chat_transcript
from openlia.llm.runtime.editor_client import (
    EditorClient,
    EditorRequest,
)
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportStart,
    SseEvent,
)
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report_context_bundle import load_bundle
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.types import ResolvedModel
from openlia.reports.validator import validate_report_payload

ResolveFn = Callable[..., ResolvedModel]
ProviderFactory = Callable[[ResolvedModel], LLMProvider]


def _load_revision_role_prompt(prompts: PromptLoader) -> str:
    p = prompts._root / "shared" / "revision_editor_role.yaml.j2"
    return p.read_text()


def _load_schema_strictness(prompts: PromptLoader) -> str:
    p = prompts._root / "shared" / "report_schema_strictness.yaml.j2"
    return p.read_text() if p.exists() else ""


class RevisionRunner:
    def __init__(
        self,
        *,
        prompts: PromptLoader,
        resolve: ResolveFn,
        registry: Any,
        flagship_provider_factory: ProviderFactory,
        report_id_factory: Callable[[], str] | None = None,
        bundle_dir: Path,
        db_session_factory: Any,
    ) -> None:
        self._prompts = prompts
        self._resolve = resolve
        self._registry = registry
        self._flagship_factory = flagship_provider_factory
        self._report_id_factory = report_id_factory or (lambda: f"r_{uuid.uuid4().hex[:12]}")
        self._bundle_dir = bundle_dir
        self._db_session_factory = db_session_factory

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        source_report_id: str,
        chat_session_id: str,
        revision_brief: str,
        sections_to_focus: list[str] | None,
    ) -> AsyncIterator[SseEvent]:
        from openlia_server.db.models.content import ChatMessage, Report

        new_report_id = self._report_id_factory()
        yield ReportStart(
            report_id=new_report_id,
            department=department_id,
            mode="revision",
            section_titles=[],
        )

        yield ReportPhase(report_id=new_report_id, phase="loading_context")

        source_bundle_path = self._bundle_dir / f"{source_report_id}.json.gz"
        if not source_bundle_path.exists():
            yield ReportError(
                report_id=new_report_id,
                error_class="bundle_missing",
                message=(
                    "Could not revise — the original report's context "
                    "bundle is no longer available."
                ),
            )
            return
        try:
            source_bundle = load_bundle(source_bundle_path)
        except Exception as exc:
            yield ReportError(
                report_id=new_report_id,
                error_class="bundle_load_failed",
                message=f"Failed to load source bundle: {exc!s}",
            )
            return

        # Load source report + chat messages.
        with self._db_session_factory() as session:
            source_row = session.get(Report, source_report_id)
            if source_row is None or source_row.content_structured is None:
                yield ReportError(
                    report_id=new_report_id,
                    error_class="source_missing",
                    message="Source report not found or has no payload.",
                )
                return
            source_schema: dict[str, Any] = source_row.content_structured
            chat_msgs = (
                session.query(ChatMessage)
                .filter(ChatMessage.session_id == chat_session_id)
                .order_by(ChatMessage.id.asc())
                .all()
            )
            chat_dicts = [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": getattr(m, "tool_calls", None),
                    "tool_call_id": getattr(m, "tool_call_id", None),
                }
                for m in chat_msgs
            ]

        chat_excerpt = compress_chat_transcript(chat_dicts)

        # Synthesize section_drafts from the source ReportSchema sections.
        synthesized_drafts: list[SectionDraft] = []
        for s in source_schema.get("sections", []):
            synthesized_drafts.append(
                SectionDraft(
                    section_id=s.get("id", ""),
                    blocks=s.get("blocks", []),
                    citations_used=[],
                    word_count=sum(
                        len(b.get("content", "").split())
                        for b in s.get("blocks", [])
                        if b.get("type") == "text"
                    ),
                    open_questions=[],
                )
            )

        yield ReportPhase(report_id=new_report_id, phase="editing")

        resolved_flag = self._resolve(
            department_id=department_id,
            user_id=user_id,
            registry=self._registry,
            role="flagship",
        )
        flagship = self._flagship_factory(resolved_flag)
        editor = EditorClient(provider=flagship, repair_budget=1, max_output_tokens=8192)

        thesis = (source_schema.get("cover") or {}).get("tagline") or ""
        themes = list(source_bundle.plan.cross_section_themes)

        editor_req = EditorRequest(
            role_prompt=_load_revision_role_prompt(self._prompts),
            style_guide="",
            schema_strictness=_load_schema_strictness(self._prompts),
            company_thesis=thesis,
            cross_section_themes=themes,
            section_drafts=synthesized_drafts,
            open_questions=[],
            framework_cover_instructions=(
                "Compose cover.title, cover.subtitle, cover.tagline, cover.tldr "
                "from the revised content. Build cover.key_metrics from the revised data."
            ),
            revision_brief=revision_brief,
            sections_to_focus=sections_to_focus,
            chat_transcript_excerpt=chat_excerpt or None,
        )
        revised_payload = await editor.compose(editor_req)

        yield ReportPhase(report_id=new_report_id, phase="finalizing")

        from openlia.llm.runtime.report import _finalize_submit_payload

        finalized = _finalize_submit_payload(
            revised_payload,
            department_id=department_id,
            generated_at=datetime.now(UTC),
            provider_citations=[],
            model_id=resolved_flag.model_ref,
            total_input_tokens=0,
            total_output_tokens=0,
            web_search_count=0,
        )
        validate_report_payload(finalized)

        # Bundle inheritance: copy source bundle to new report id path.
        new_bundle_path = self._bundle_dir / f"{new_report_id}.json.gz"
        try:
            shutil.copy2(source_bundle_path, new_bundle_path)
        except Exception:
            # Non-fatal — report still ships.
            pass

        yield ReportComplete(report_id=new_report_id, schema=finalized)
