"""Parallel section writer dispatch with per-section retry and terminal-state tracking."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
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


_DIAGNOSTIC_DIR = Path("/tmp/report_v2_failed_sections")
_PARSE_ERROR_TERMS = ("frontmatter", "parse")


def _format_errors(findings: list[ValidationFinding]) -> str:
    return "\n".join(f"- {f.check}: {f.detail}" for f in findings)


def _is_parse_error(errors: list[str]) -> bool:
    return any(term in e for e in errors for term in _PARSE_ERROR_TERMS)


def _maybe_write_diagnostic(result: SectionResult) -> None:
    if result.state != SectionTerminalState.EXHAUSTED:
        return
    if not result.failed_attempts:
        return
    if not _is_parse_error(result.validation_errors):
        return
    try:
        _DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
        out = _DIAGNOSTIC_DIR / f"{result.section_id}.md"
        # Write the LAST failed attempt (the one matching validation_errors).
        out.write_text(result.failed_attempts[-1], encoding="utf-8")
        print(
            f"[diagnostic] wrote last failed attempt of {result.section_id} to {out}",
            flush=True,
        )
    except Exception as exc:
        print(
            f"[diagnostic] warning: could not write diagnostic for {result.section_id}: {exc}",
            flush=True,
        )


async def _dispatch_one(
    *,
    d: SectionDispatch,
    writer: SectionWriter,
    validator: Callable[..., list[ValidationFinding]],
    max_retries: int,
    known_block_tags: list[str],
    concurrency_semaphore: asyncio.Semaphore | None = None,
) -> SectionResult:
    attempts = 0
    failed_attempts: list[str] = []
    last_errors: list[ValidationFinding] = []
    prompt = d.prompt

    while attempts <= max_retries:
        attempts += 1
        if concurrency_semaphore is not None:
            async with concurrency_semaphore:
                raw = await writer.write(prompt)
        else:
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
            break

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

    exhausted = SectionResult(
        section_id=d.section_id,
        state=SectionTerminalState.EXHAUSTED,
        attempts=attempts,
        failed_attempts=failed_attempts,
        validation_errors=[f.detail for f in last_errors],
    )
    _maybe_write_diagnostic(exhausted)
    return exhausted


async def dispatch_sections(
    *,
    dispatches: list[SectionDispatch],
    writer: SectionWriter,
    validator: Callable[..., list[ValidationFinding]],
    max_retries: int,
    known_block_tags: list[str],
    concurrency_semaphore: asyncio.Semaphore | None = None,
) -> list[SectionResult]:
    # Use sequential iteration with fail-fast only when concurrency is capped to 1.
    # fail-fast only fires when concurrency_semaphore caps to 1.
    sequential = (
        concurrency_semaphore is not None
        and getattr(concurrency_semaphore, "_value", None) == 1
    )
    if not sequential:
        tasks = [
            _dispatch_one(
                d=d,
                writer=writer,
                validator=validator,
                max_retries=max_retries,
                known_block_tags=known_block_tags,
                concurrency_semaphore=concurrency_semaphore,
            )
            for d in dispatches
        ]
        return list(await asyncio.gather(*tasks))

    # Sequential loop with fail-fast on systemic parse error in first section.
    results: list[SectionResult] = []
    for i, d in enumerate(dispatches):
        result = await _dispatch_one(
            d=d,
            writer=writer,
            validator=validator,
            max_retries=max_retries,
            known_block_tags=known_block_tags,
            concurrency_semaphore=concurrency_semaphore,
        )
        results.append(result)
        if (
            i == 0
            and result.state == SectionTerminalState.EXHAUSTED
            and _is_parse_error(result.validation_errors)
        ):
            print(
                "[dispatch] first section exhausted on parse error; skipping remaining sections.",
                flush=True,
            )
            for remaining in dispatches[i + 1 :]:
                results.append(
                    SectionResult(
                        section_id=remaining.section_id,
                        state=SectionTerminalState.EXHAUSTED,
                        attempts=0,
                        failed_attempts=[],
                        validation_errors=[
                            "skipped: prior section exhausted on systemic parse error"
                        ],
                    )
                )
            return results
    return results
