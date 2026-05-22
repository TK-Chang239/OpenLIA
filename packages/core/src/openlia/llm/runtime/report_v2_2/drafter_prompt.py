"""Stage 7b drafter prompt builder.

Per artifact-injection §6. Builds the LLM-facing prompt for drafting one section.
Pure-Python, no LLM calls.
"""

from __future__ import annotations

from .materialize import MaterializedSection


def build_drafter_prompt(
    section: MaterializedSection,
    template_section_meta: dict,  # title / description / style from template
    thesis: str,  # cross-section thesis from earlier stage
    themes: list[str],  # cross-section themes
    threading_summaries: list[str] | None = None,  # prior section summaries
    template_id: str | None = None,  # e.g. "stock_initiation_v2"
    ticker: str | None = None,  # e.g. "MSFT"
) -> str:
    """Build the LLM-facing prompt for Stage 7b drafting one section.

    Structure per artifact-injection §6:
    1. System role: section subagent (with template_id/ticker context when provided)
    2. Thesis + themes
    3. Section metadata (title, word_budget, style)
    4. Materialized artifacts (each with provenance header)
    5. Open questions to address
    6. Prior section summaries (threading)
    7. Output schema instructions
    """
    parts: list[str] = []

    # 1. System role (per artifact-injection §6 — include template_id and ticker if provided)
    if template_id and ticker:
        parts.append(f"You are drafting {template_id} for {ticker}.")
    parts.append("You are a section subagent drafting one section of an equity research report.")
    parts.append(
        "Ground every claim in the artifacts provided. "
        "Do not invent numbers not present in artifacts."
    )
    parts.append("")

    # 2. Thesis + themes
    parts.append("## Investment Thesis")
    parts.append(thesis.strip())
    parts.append("")
    if themes:
        parts.append("## Cross-Section Themes")
        for theme in themes:
            parts.append(f"- {theme}")
        parts.append("")

    # 3. Section metadata
    title = template_section_meta.get("title", section.title)
    description = template_section_meta.get("description", "")
    style = template_section_meta.get("style", "")
    min_words: int | None = template_section_meta.get("min_words")
    tolerance_pct: int | None = template_section_meta.get("tolerance_pct")
    expand_below_pct: int | None = template_section_meta.get("expand_below_pct")

    parts.append("## Section to Draft")
    parts.append(f"**Title:** {title}")
    if description:
        parts.append(f"**Description:** {description}")
    if style:
        parts.append(f"**Style:** {style}")
    if min_words is not None:
        parts.append(f"**Minimum words:** {min_words}")
    if tolerance_pct is not None:
        parts.append(f"**Word-count tolerance:** ±{tolerance_pct}%")
    if expand_below_pct is not None:
        parts.append(
            f"**Expand if below:** {expand_below_pct}% of the word budget — add analysis, "
            "not padding."
        )
    parts.append("")

    # 4. Materialized artifacts
    if section.rendered_artifacts:
        parts.append("## Artifacts")
        parts.append(
            "Each artifact below was produced by the specified helper at the specified fidelity. "
            "Render the artifact verbatim in your draft, then surround it with prose that "
            "interprets it."
        )
        parts.append("")
        for art in section.rendered_artifacts:
            parts.append(
                f"### Artifact: `{art.artifact_id}` "
                f"(produced by `{art.helper_name}` at `{art.fidelity.value}` fidelity)"
            )
            parts.append(art.content)
            parts.append("")
    else:
        parts.append("## Artifacts")
        parts.append("_No artifacts materialized for this section._")
        parts.append("")

    # 5. Open questions
    if section.open_questions:
        parts.append("## Open Questions to Address")
        for q in section.open_questions:
            parts.append(f"- {q}")
        parts.append("")

    # 6. Prior section summaries (threading)
    if threading_summaries:
        parts.append("## Prior Section Context (Threading)")
        parts.append("Brief summaries of preceding sections. Do not repeat these — build on them.")
        for i, summary in enumerate(threading_summaries, 1):
            parts.append(f"**Section {i} summary:** {summary.strip()}")
        parts.append("")

    # 7. Output schema instructions
    parts.append("## Output Instructions")
    parts.append("Write the section prose in Markdown. Your output must:")
    parts.append(f"- Start with `## {title}` as the section heading.")
    parts.append("- Include each artifact rendered above, verbatim, in its appropriate place.")
    parts.append(
        "- For back-referenced artifacts (marked 'See ... above'), cite by section name only — "
        "do not re-state the full data."
    )
    parts.append("- Anchor the section thesis in the first paragraph.")
    parts.append("- Do not invent numbers not present in the artifacts.")
    parts.append("")

    return "\n".join(parts)
