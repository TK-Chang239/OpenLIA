"""Parallel section writer dispatch with per-section retry and terminal-state tracking."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from openlia.llm.runtime.report_v2.packer.auto_repair import repair_section
from openlia.llm.runtime.report_v2.packer.parser import parse_section_file
from openlia.llm.runtime.report_v2.packer.validator import ValidationFinding
from openlia.llm.runtime.report_v2.types import (
    Fact,
    SectionResult,
    SectionTerminalState,
)


class SectionWriter(Protocol):
    async def write(self, prompt: str) -> str: ...


@dataclass
class SectionDispatch:
    section_id: str
    prompt: str
    target_word_count: int
    facts_slice: dict[str, Fact]


def _format_errors(findings: list[ValidationFinding]) -> str:
    return "\n".join(f"- {f.check}: {f.detail}" for f in findings)


async def _dispatch_one(
    *,
    d: SectionDispatch,
    writer: SectionWriter,
    validator: Callable[..., list[ValidationFinding]],
    max_retries: int,
    known_block_tags: list[str],
) -> SectionResult:
    attempts = 0
    failed_attempts: list[str] = []
    last_errors: list[ValidationFinding] = []
    prompt = d.prompt

    while attempts <= max_retries:
        attempts += 1
        raw = await writer.write(prompt)
        repair = repair_section(raw, known_tags=known_block_tags)
        markdown = repair.markdown
        try:
            parsed = parse_section_file(markdown)
        except ValueError as e:
            last_errors = [
                ValidationFinding(
                    check="parse_error", section_id=d.section_id, detail=str(e)
                )
            ]
            failed_attempts.append(raw)
            if attempts <= max_retries:
                prompt = (
                    f"{d.prompt}\n\nPREVIOUS ATTEMPT FAILED PARSE:\n{e}"
                    "\n\nRe-emit the section."
                )
                continue
            return SectionResult(
                section_id=d.section_id,
                state=SectionTerminalState.EXHAUSTED,
                attempts=attempts,
                failed_attempts=failed_attempts,
                validation_errors=[f.detail for f in last_errors],
            )

        errors = [
            f
            for f in validator(
                parsed,
                facts_slice=d.facts_slice,
                target_word_count=d.target_word_count,
            )
            if f.severity == "error"
        ]
        if not errors:
            state = (
                SectionTerminalState.SUCCESS
                if attempts == 1 and not repair.fixes_applied
                else SectionTerminalState.DEGRADED
            )
            return SectionResult(
                section_id=d.section_id,
                state=state,
                attempts=attempts,
                markdown=markdown,
                failed_attempts=failed_attempts,
                validation_errors=[],
            )

        failed_attempts.append(raw)
        last_errors = errors
        if attempts <= max_retries:
            prompt = (
                f"{d.prompt}\n\nYOUR PREVIOUS ATTEMPT FAILED VALIDATION:\n"
                f"{_format_errors(errors)}\n\nRe-emit the section. Address each error explicitly."
            )

    return SectionResult(
        section_id=d.section_id,
        state=SectionTerminalState.EXHAUSTED,
        attempts=attempts,
        failed_attempts=failed_attempts,
        validation_errors=[f.detail for f in last_errors],
    )


async def dispatch_sections(
    *,
    dispatches: list[SectionDispatch],
    writer: SectionWriter,
    validator: Callable[..., list[ValidationFinding]],
    max_retries: int,
    known_block_tags: list[str],
) -> list[SectionResult]:
    tasks = [
        _dispatch_one(
            d=d,
            writer=writer,
            validator=validator,
            max_retries=max_retries,
            known_block_tags=known_block_tags,
        )
        for d in dispatches
    ]
    return list(await asyncio.gather(*tasks))
