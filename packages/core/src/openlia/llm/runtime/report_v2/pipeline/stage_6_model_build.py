"""Stage 6 — Model build: parallel artifact construction with param resolution.

See docs/superpowers/plans/2026-05-21-equity-research-v2.2.md §P5.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.pipeline.param_resolver import resolve_params
from openlia.llm.runtime.report_v2.schemas.plan import ArtifactSpec
from openlia.llm.runtime.report_v2.tools.library_helpers import get_helper


@dataclass
class ModelArtifact:
    spec: ArtifactSpec
    status: str  # "OK" | "FAILED"
    content: Any = None
    resolved_params: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    failure_reason: str | None = None


class ModelBuilder:
    def __init__(self, llm: Any, max_workers: int = 4) -> None:
        self.llm = llm
        self.max_workers = max_workers

    def build(
        self,
        artifacts: list[ArtifactSpec],
        research_pool: Any,
    ) -> list[ModelArtifact]:
        results: list[ModelArtifact] = [None] * len(artifacts)  # type: ignore[list-item]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(self._build_one, spec, research_pool): i
                for i, spec in enumerate(artifacts)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()

        return results

    def _build_one(self, spec: ArtifactSpec, research_pool: Any) -> ModelArtifact:
        # Guard: no helper assigned
        if spec.helper is None:
            return ModelArtifact(
                spec=spec,
                status="FAILED",
                failure_reason=(
                    "no helper assigned and planner-pick path not implemented in v2.2 P5"
                ),
            )

        # Guard: helper not registered
        try:
            helper = get_helper(spec.helper)
        except KeyError:
            return ModelArtifact(
                spec=spec,
                status="FAILED",
                failure_reason=f"helper {spec.helper!r} not registered",
            )

        # Guard: helper deferred
        if not helper.available:
            return ModelArtifact(
                spec=spec,
                status="FAILED",
                failure_reason=(
                    f"helper {spec.helper!r} is in deferred category {helper.deferred_category!r}"
                ),
            )

        # Resolve params
        resolver = resolve_params(spec.helper, spec.parameters, research_pool, self.llm)
        if resolver.failed:
            return ModelArtifact(
                spec=spec,
                status="FAILED",
                resolved_params=resolver.resolved,
                provenance=resolver.provenance,
                failure_reason=resolver.reason,
            )

        # Execute with one retry
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                content = helper.execute(**resolver.resolved)
                return ModelArtifact(
                    spec=spec,
                    status="OK",
                    content=content,
                    resolved_params=resolver.resolved,
                    provenance=resolver.provenance,
                )
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    continue

        return ModelArtifact(
            spec=spec,
            status="FAILED",
            resolved_params=resolver.resolved,
            provenance=resolver.provenance,
            failure_reason=f"helper raised: {last_error}",
        )
