"""Stage 4 gather — parallel strand dispatcher with retry-once and cache-stat aggregation.

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §4.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from openlia.llm.runtime.report_v2.schemas.plan import ResearchStrand
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation, ResearchPool


class StrandDispatcher:
    """Dispatches research strands in parallel with retry-once semantics."""

    def __init__(self, subagent: Any, max_workers: int = 4) -> None:
        self._subagent = subagent
        self._max_workers = max_workers

    def dispatch(
        self,
        strands: list[ResearchStrand],
        composer_inputs: dict[str, Any],
        plan: Any,
    ) -> ResearchPool:
        pool = ResearchPool()
        futures = {}

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            for strand in strands:
                future = executor.submit(
                    self._run_strand_with_retry,
                    strand,
                    composer_inputs,
                    plan,
                )
                futures[future] = strand

            for future in as_completed(futures):
                strand = futures[future]
                try:
                    result = future.result()
                except Exception:
                    pool.failed_strands.append(strand.id)
                    continue

                pool.findings_by_strand[strand.id] = result.get("findings", "")

                for c in result.get("citations", []):
                    if isinstance(c, Citation):
                        pool.citations.append(c)
                    else:
                        pool.citations.append(Citation(**c))

                pool.cache_hits += result.get("cache_hits", 0)
                pool.cache_misses += result.get("cache_misses", 0)

        return pool

    def _run_strand_with_retry(
        self,
        strand: ResearchStrand,
        composer_inputs: dict[str, Any],
        plan: Any,
    ) -> dict[str, Any]:
        try:
            return self._subagent.run(
                strand=strand,
                composer_inputs=composer_inputs,
                plan=plan,
            )
        except Exception:
            pass

        return self._subagent.run(
            strand=strand,
            composer_inputs=composer_inputs,
            plan=plan,
        )
