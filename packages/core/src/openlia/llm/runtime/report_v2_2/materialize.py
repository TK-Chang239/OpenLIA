"""Stage 7a materialization: pure-Python, deterministic, zero LLM calls.

Per artifact-injection §5. Takes a resolved ReportSectionPlan + Stage 6 helper
outputs and produces sectioned markdown that Stage 7b drafter narrates.

Design choices:
- Highest-fidelity-wins per artifact_id (B3 dedup, §5.1).
- First section in document order becomes canonical render site.
- Later sections back-reference with a headline recap if lower fidelity wanted.
- Orphan artifacts (produced but not referenced) are dropped silently.
- Missing artifacts emit BLOCK_PLAN_ARTIFACT_MISSING into warnings, skip artifact.
- Oversize rendered output emits BLOCK_ARTIFACT_TOO_LARGE + truncates.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel

from .enums import Fidelity, VerifierIssueType
from .section_plan import (
    PlannerOverrides,
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
    SectionPlanOverride,
)
from .verifier_models import VerifierIssue

if TYPE_CHECKING:
    from .telemetry import TelemetryCollector

# ---- token / char size caps per artifact-injection §2.2 ----
# 1 token ≈ 4 chars (heuristic).
_HARD_CAP_CHARS: dict[Fidelity, int] = {
    Fidelity.HEADLINE: 120 * 4,  # 480 chars
    Fidelity.SUMMARY: 600 * 4,  # 2400 chars
    Fidelity.FULL: 3000 * 4,  # 12000 chars
}

# Internal guard: always truncate at FULL hard cap regardless of fidelity
# so a default renderer on an unexpectedly large artifact can't blow the prompt.
_ABSOLUTE_SIZE_CAP_CHARS = _HARD_CAP_CHARS[Fidelity.FULL]

_TRUNCATION_SUFFIX = "\n[truncated]"

_MATERIALIZATION_HELPER = "__materialization__"


# ---------------------------------------------------------------------------
# Projector / Renderer protocols + default implementations
# ---------------------------------------------------------------------------


@runtime_checkable
class ArtifactProjector(Protocol):
    def project(self, raw: Any, fidelity: Fidelity) -> dict[str, Any]: ...


@runtime_checkable
class ArtifactRenderer(Protocol):
    def render(self, projected: dict[str, Any], fidelity: Fidelity) -> str: ...


class DefaultProjector:
    """Returns raw dict as-is for FULL; selects top-level scalar fields for
    SUMMARY; uses the first scalar field's value as a one-liner for HEADLINE.

    Per task spec: 'Default projector: returns raw as-is for FULL; selects key
    fields for SUMMARY; first-line for HEADLINE'.
    """

    def project(self, raw: Any, fidelity: Fidelity) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raw = {"value": str(raw)}
        if fidelity == Fidelity.FULL:
            return raw
        # Extract scalar (non-dict, non-list) top-level fields.
        scalars = {k: v for k, v in raw.items() if not isinstance(v, (dict, list))}
        if fidelity == Fidelity.SUMMARY:
            return scalars if scalars else raw
        # HEADLINE: first scalar field only.
        if scalars:
            first_key = next(iter(scalars))
            return {first_key: scalars[first_key]}
        return {next(iter(raw)): next(iter(raw.values()))}


class DefaultRenderer:
    """Renders a projected dict as GitHub-flavored Markdown.

    - If projected is a list of dicts: Markdown table, numeric columns right-aligned.
    - Otherwise: bullet list of `**key**: value` pairs.

    Per task spec: 'Default renderer: emits a Markdown bullet list of
    "key: value" pairs, or a Markdown table if raw is a list of dicts'.
    """

    def render(self, projected: dict[str, Any], fidelity: Fidelity) -> str:
        if not projected:
            return "_No data._"
        # Check if it is a single key wrapping a list of dicts (common helper pattern).
        if len(projected) == 1:
            sole_val = next(iter(projected.values()))
            if isinstance(sole_val, list) and sole_val and isinstance(sole_val[0], dict):
                return _render_table(sole_val)
        # Plain dict → bullet list.
        lines: list[str] = []
        for k, v in projected.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                lines.append(f"**{k}**:")
                lines.append(_render_table(v))
            elif isinstance(v, list):
                inner = ", ".join(str(x) for x in v)
                lines.append(f"- **{k}**: {inner}")
            elif isinstance(v, dict):
                inner = "; ".join(f"{ik}: {iv}" for ik, iv in v.items())
                lines.append(f"- **{k}**: {inner}")
            else:
                lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)


def _render_table(rows: list[dict[str, Any]]) -> str:
    """GitHub-flavored markdown table. Numeric columns right-aligned (---:)."""
    if not rows:
        return ""
    headers = list(rows[0].keys())

    def _is_numeric_col(col: str) -> bool:
        return all(isinstance(r.get(col), (int, float)) for r in rows if col in r)

    header_row = "| " + " | ".join(str(h) for h in headers) + " |"
    sep_parts = ["---:" if _is_numeric_col(h) else "---" for h in headers]
    sep_row = "| " + " | ".join(sep_parts) + " |"
    data_rows = []
    for row in rows:
        cells = [str(row.get(h, "")) for h in headers]
        data_rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_row, sep_row, *data_rows])


_default_projector = DefaultProjector()
_default_renderer = DefaultRenderer()

_PROJECTORS: dict[str, ArtifactProjector] = {}
_RENDERERS: dict[str, ArtifactRenderer] = {}


def register_projector(artifact_type: str, projector: ArtifactProjector) -> None:
    _PROJECTORS[artifact_type] = projector


def register_renderer(artifact_type: str, renderer: ArtifactRenderer) -> None:
    _RENDERERS[artifact_type] = renderer


def _get_projector(artifact_type: str) -> ArtifactProjector:
    return _PROJECTORS.get(artifact_type, _default_projector)


def _get_renderer(artifact_type: str) -> ArtifactRenderer:
    return _RENDERERS.get(artifact_type, _default_renderer)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class RenderedArtifact(BaseModel):
    artifact_id: str
    artifact_type: str
    helper_name: str
    fidelity: Fidelity
    content: str  # markdown
    raw_data: dict[str, Any]  # for verifier coherence checks


class MaterializedSection(BaseModel):
    section_id: str
    title: str
    rendered_artifacts: list[RenderedArtifact]  # ordered by section_plan
    open_questions: list[str] = []
    cross_section_themes: list[str] = []
    materialization_warnings: list[VerifierIssue] = []  # non-blocking signals


class MaterializedReport(BaseModel):
    """Full report materialization: all sections + the deduplicated markdown string."""

    template_id: str
    sections: list[MaterializedSection]
    markdown: str  # complete materialized markdown for Stage 7b
    orphan_artifact_ids: list[str] = []  # produced by Stage 6 but not referenced


# ---------------------------------------------------------------------------
# Plan resolution (override application) — §4.3
# ---------------------------------------------------------------------------


class PlanResolutionError(ValueError):
    """Raised when override resolution fails at Stage 7a precondition."""


def _apply_override(section: SectionPlan, ov: SectionPlanOverride) -> None:
    if ov.operation == "add":
        if ov.artifact_id is None or ov.fidelity is None:
            raise PlanResolutionError(
                f"override 'add' on section {section.section_id!r} "
                "requires artifact_id and fidelity"
            )
        section.artifacts.append(
            SectionArtifactRef(artifact_id=ov.artifact_id, fidelity=ov.fidelity)
        )

    elif ov.operation == "remove":
        if ov.artifact_id is None:
            raise PlanResolutionError(
                f"override 'remove' on section {section.section_id!r} requires artifact_id"
            )
        original = len(section.artifacts)
        section.artifacts = [a for a in section.artifacts if a.artifact_id != ov.artifact_id]
        if len(section.artifacts) == original:
            raise PlanResolutionError(
                f"override 'remove' on section {section.section_id!r}: "
                f"artifact_id {ov.artifact_id!r} not found"
            )

    elif ov.operation == "change_fidelity":
        if ov.artifact_id is None or ov.fidelity is None:
            raise PlanResolutionError(
                f"override 'change_fidelity' on section {section.section_id!r} requires "
                "artifact_id and fidelity"
            )
        matched = False
        for ref in section.artifacts:
            if ref.artifact_id == ov.artifact_id:
                ref.fidelity = ov.fidelity
                matched = True
        if not matched:
            raise PlanResolutionError(
                f"override 'change_fidelity' on section {section.section_id!r}: "
                f"artifact_id {ov.artifact_id!r} not found"
            )

    elif ov.operation == "add_brief":
        if ov.drafter_brief is None:
            raise PlanResolutionError(
                f"override 'add_brief' on section {section.section_id!r} requires drafter_brief"
            )
        section.drafter_brief = ov.drafter_brief

    else:
        raise PlanResolutionError(f"unknown override operation {ov.operation!r}")


def _describe_override(ov: SectionPlanOverride) -> str:
    parts = [f"section={ov.section_id}", f"op={ov.operation}"]
    if ov.artifact_id:
        parts.append(f"artifact={ov.artifact_id}")
    if ov.fidelity:
        parts.append(f"fidelity={ov.fidelity}")
    return " ".join(parts)


def resolve_section_plan(
    template_defaults: ReportSectionPlan,
    overrides: PlannerOverrides | None,
) -> ReportSectionPlan:
    """Apply planner overrides to template defaults in declaration order.

    Per artifact-injection §4.3. Override failures are hard errors (PlanResolutionError).
    """
    plan = template_defaults.model_copy(deep=True)
    if overrides is None:
        return plan
    applied: list[str] = []
    for ov in overrides.overrides:
        section = next((s for s in plan.sections if s.section_id == ov.section_id), None)
        if section is None:
            raise PlanResolutionError(f"override references unknown section {ov.section_id!r}")
        _apply_override(section, ov)
        applied.append(_describe_override(ov))
    plan.overrides_applied = applied
    return plan


# ---------------------------------------------------------------------------
# Highest-fidelity-wins dedup helper — §5.1
# ---------------------------------------------------------------------------

_FIDELITY_RANK: dict[Fidelity, int] = {
    Fidelity.HEADLINE: 0,
    Fidelity.SUMMARY: 1,
    Fidelity.FULL: 2,
}


def _highest_fidelity_per_artifact(plan: ReportSectionPlan) -> dict[str, Fidelity]:
    """Return the highest fidelity requested for each artifact_id across all sections."""
    highest: dict[str, Fidelity] = {}
    for section in plan.sections:
        for ref in section.artifacts:
            current = highest.get(ref.artifact_id)
            if current is None or _FIDELITY_RANK[ref.fidelity] > _FIDELITY_RANK[current]:
                highest[ref.artifact_id] = ref.fidelity
    return highest


# ---------------------------------------------------------------------------
# Render one artifact to markdown
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"\d")


def _render_artifact(
    artifact_id: str,
    raw: Any,
    fidelity: Fidelity,
) -> tuple[str, list[VerifierIssue]]:
    """Project + render one artifact. Returns (markdown, warnings).

    Applies size cap from §2.2; emits BLOCK_ARTIFACT_TOO_LARGE if exceeded.
    """
    warnings: list[VerifierIssue] = []

    # Infer artifact_type: check if raw has an artifact_type attr, else use artifact_id.
    artifact_type: str = getattr(raw, "artifact_type", None) or artifact_id

    projector = _get_projector(artifact_type)
    renderer = _get_renderer(artifact_type)

    raw_dict: dict[str, Any]
    if isinstance(raw, dict):
        raw_dict = raw
    elif hasattr(raw, "model_dump"):
        raw_dict = raw.model_dump()
    else:
        raw_dict = {"value": str(raw)}

    projected = projector.project(raw_dict, fidelity)
    content = renderer.render(projected, fidelity)

    # §2.2 headline quantitative check.
    if fidelity == Fidelity.HEADLINE and not _NUMERIC_RE.search(content):
        warnings.append(
            VerifierIssue(
                type=VerifierIssueType.BLOCK_HEADLINE_MISSING_QUANTITATIVE,
                detail_code="no_numeric_anchor",
                severity="advisory",
                helper=_MATERIALIZATION_HELPER,
                detail=(
                    f"Headline for artifact {artifact_id!r} contains no quantitative anchor. "
                    "Headline must include at least one number."
                ),
            )
        )

    cap = _HARD_CAP_CHARS.get(fidelity, _ABSOLUTE_SIZE_CAP_CHARS)
    if len(content) > cap:
        warnings.append(
            VerifierIssue(
                type=VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE,
                detail_code="oversize",
                severity="blocking",
                helper=_MATERIALIZATION_HELPER,
                detail=(
                    f"Artifact {artifact_id!r} at fidelity {fidelity.value!r} "
                    f"rendered {len(content)} chars, exceeds hard cap {cap}."
                ),
            )
        )
        content = content[:cap] + _TRUNCATION_SUFFIX

    return content, warnings


# ---------------------------------------------------------------------------
# Core materialize_section function (task spec signature)
# ---------------------------------------------------------------------------


def materialize_section(
    plan: SectionPlan,
    helper_outputs: dict[str, Any],
    *,
    fidelity_override: dict[str, Fidelity] | None = None,
    telemetry: TelemetryCollector | None = None,
) -> MaterializedSection:
    """Materialize one section. Per task spec §2.

    For each helper_invocation (here: each SectionArtifactRef) in plan:
    1. Look up artifact from helper_outputs keyed by artifact_id.
    2. Determine fidelity (from fidelity_override or plan).
    3. Project + render.
    4. Wrap in RenderedArtifact.
    Emits BLOCK_PLAN_ARTIFACT_MISSING for missing outputs; BLOCK_ARTIFACT_TOO_LARGE
    for oversize artifacts.
    """
    warnings: list[VerifierIssue] = []
    rendered: list[RenderedArtifact] = []

    for ref in plan.artifacts:
        if ref.artifact_id not in helper_outputs:
            warnings.append(
                VerifierIssue(
                    type=VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING,
                    detail_code=ref.artifact_id,
                    severity="blocking",
                    helper=_MATERIALIZATION_HELPER,
                    detail=(
                        f"Section {plan.section_id!r} references artifact "
                        f"{ref.artifact_id!r} which is not in helper_outputs."
                    ),
                )
            )
            continue

        raw = helper_outputs[ref.artifact_id]
        effective_fidelity = (
            fidelity_override.get(ref.artifact_id, ref.fidelity)
            if fidelity_override
            else ref.fidelity
        )

        content, render_warnings = _render_artifact(ref.artifact_id, raw, effective_fidelity)
        warnings.extend(render_warnings)

        # Determine raw_data for verifier coherence checks.
        if isinstance(raw, dict):
            raw_data = raw
        elif hasattr(raw, "model_dump"):
            raw_data = raw.model_dump()
        else:
            raw_data = {"value": str(raw)}

        artifact_type: str = getattr(raw, "artifact_type", None) or ref.artifact_id
        was_truncated = content.endswith(_TRUNCATION_SUFFIX)

        if telemetry is not None:
            telemetry.record_materialize(
                section_id=plan.section_id,
                artifact_id=ref.artifact_id,
                helper_name=_MATERIALIZATION_HELPER,
                fidelity=effective_fidelity.value,
                rendered_chars=len(content),
                was_truncated=was_truncated,
            )

        rendered.append(
            RenderedArtifact(
                artifact_id=ref.artifact_id,
                artifact_type=artifact_type,
                helper_name=_MATERIALIZATION_HELPER,
                fidelity=effective_fidelity,
                content=content,
                raw_data=raw_data,
            )
        )

    return MaterializedSection(
        section_id=plan.section_id,
        title=plan.title,
        rendered_artifacts=rendered,
        materialization_warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Full-report materialize() — §5 algorithm
# ---------------------------------------------------------------------------


def materialize(
    section_plan: ReportSectionPlan,
    artifacts: dict[str, Any],
    *,
    telemetry: TelemetryCollector | None = None,
) -> MaterializedReport:
    """Materialize a full report: resolve dedup, render, produce sectioned markdown.

    Per artifact-injection §5. Deterministic: same inputs → byte-identical output.
    """
    # Step 1: precondition check — raise hard error on missing artifacts.
    referenced_ids = {ref.artifact_id for s in section_plan.sections for ref in s.artifacts}
    missing = referenced_ids - artifacts.keys()
    if missing:
        raise MaterializationError(
            f"section_plan references {sorted(missing)!r}, not in Stage 6 output"
        )

    # Step 2: highest-fidelity-wins per artifact_id (B3 dedup).
    highest = _highest_fidelity_per_artifact(section_plan)

    # Step 3: render per-section with dedup + back-references.
    rendered_sites: dict[str, str] = {}  # artifact_id → anchor of canonical render
    all_warnings: list[VerifierIssue] = []
    section_models: list[MaterializedSection] = []
    out: list[str] = []

    for section in section_plan.sections:
        out.append(f"\n## {section.title}\n")
        if section.drafter_brief:
            out.append(f"_Brief: {section.drafter_brief}_\n")

        section_rendered: list[RenderedArtifact] = []
        section_warnings: list[VerifierIssue] = []

        for ref in section.artifacts:
            art = artifacts[ref.artifact_id]
            anchor = f"#{section.section_id}__{ref.artifact_id}"

            if ref.artifact_id not in rendered_sites:
                # Canonical site: render at highest fidelity needed anywhere.
                canonical_level = highest[ref.artifact_id]
                out.append(f'<a id="{anchor.lstrip("#")}"></a>\n')

                content, render_warnings = _render_artifact(ref.artifact_id, art, canonical_level)
                section_warnings.extend(render_warnings)
                all_warnings.extend(render_warnings)

                out.append(content)
                rendered_sites[ref.artifact_id] = anchor
                out.append("\n")

                if isinstance(art, dict):
                    raw_data = art
                elif hasattr(art, "model_dump"):
                    raw_data = art.model_dump()
                else:
                    raw_data = {"value": str(art)}

                artifact_type = getattr(art, "artifact_type", None) or ref.artifact_id

                if telemetry is not None:
                    telemetry.record_materialize(
                        section_id=section.section_id,
                        artifact_id=ref.artifact_id,
                        helper_name=_MATERIALIZATION_HELPER,
                        fidelity=canonical_level.value,
                        rendered_chars=len(content),
                        was_truncated=content.endswith(_TRUNCATION_SUFFIX),
                    )

                section_rendered.append(
                    RenderedArtifact(
                        artifact_id=ref.artifact_id,
                        artifact_type=artifact_type,
                        helper_name=_MATERIALIZATION_HELPER,
                        fidelity=canonical_level,
                        content=content,
                        raw_data=raw_data,
                    )
                )
            else:
                # Subsequent site: back-reference to canonical.
                canonical = rendered_sites[ref.artifact_id]
                canonical_level = highest[ref.artifact_id]
                if ref.fidelity == canonical_level:
                    out.append(f"_See [{ref.artifact_id}]({canonical}) above._\n")
                else:
                    # Lower fidelity wanted here; emit a headline recap.
                    headline_content, headline_warnings = _render_artifact(
                        ref.artifact_id, art, Fidelity.HEADLINE
                    )
                    section_warnings.extend(headline_warnings)
                    all_warnings.extend(headline_warnings)
                    out.append(headline_content)
                    out.append(f"\n_Full detail: [{ref.artifact_id}]({canonical}) above._\n")
                out.append("\n")

        section_models.append(
            MaterializedSection(
                section_id=section.section_id,
                title=section.title,
                rendered_artifacts=section_rendered,
                materialization_warnings=section_warnings,
            )
        )

    # Orphan detection: produced but not referenced.
    orphans = sorted(artifacts.keys() - referenced_ids)

    return MaterializedReport(
        template_id=section_plan.template_id,
        sections=section_models,
        markdown="".join(out),
        orphan_artifact_ids=orphans,
    )


class MaterializationError(ValueError):
    """Hard error raised when section_plan references artifacts absent from Stage 6 output."""
