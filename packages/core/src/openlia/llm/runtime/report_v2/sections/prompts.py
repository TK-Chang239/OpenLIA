"""Section prompt assembly.

Cache-ordered: stable across runs -> stable within run -> per-section dynamic.
"""
from __future__ import annotations

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.types import Fact

# All 22 supported fenced block tags.
_OUTPUT_FORMAT_REMINDER = """\
Output format: Markdown file.
- YAML frontmatter with: section_id, title, sources_used (list of [N] manifest ids you cite), \
synthesis_hooks (only for body sections)
- Markdown body for prose; use [N] inline markers to cite manifest entries
- Typed fenced YAML blocks for structured exhibits: \
```table, \
```chart:combo, \
```metric_cards, \
```key_finding, \
```bullet_list, \
```comparison_split, \
```quote, \
```timeline, \
```pull_quote, \
```rating_badge, \
```callout_grid, \
```chart:line, \
```chart:bar, \
```chart:area, \
```chart:pie, \
```chart:candlestick, \
```chart:waterfall, \
```chart:scatter, \
```chart:heatmap, \
```chart:treemap, \
```group, \
```text
- Each block carries a `sources: [N, ...]` list of manifest ids
- Do not invent citations; only cite [N] markers that resolve to entries in the manifest above.\
"""


def _format_facts_slice(facts_slice: dict[str, Fact]) -> str:
    lines: list[str] = []
    for name, f in facts_slice.items():
        sources = ", ".join(str(s) for s in f.source_ids)
        lines.append(f"  {name}: {f.value!r} (sources: [{sources}])")
    return "\n".join(lines) if lines else "  (none)"


def assemble_body_section_prompt(
    *,
    system_role: str,
    style_guide: str,
    framework_brief: str,
    manifest: Manifest,
    facts_slice: dict[str, Fact],
    word_target: int,
) -> str:
    return "\n\n".join([
        system_role,
        f"STYLE GUIDE:\n{style_guide}",
        f"FRAMEWORK SECTION BRIEF:\n{framework_brief}",
        f"MANIFEST (citable as [N]):\n{manifest.as_prompt_list()}",
        f"FACTS FOR THIS SECTION:\n{_format_facts_slice(facts_slice)}",
        f"Word target: {word_target}",
        _OUTPUT_FORMAT_REMINDER,
    ])


def assemble_synthesis_section_prompt(
    *,
    system_role: str,
    style_guide: str,
    framework_brief: str,
    manifest: Manifest,
    synthesis_hooks_bundle: str,
    facts_slice: dict[str, Fact],
    word_target: int,
) -> str:
    return "\n\n".join([
        system_role,
        f"STYLE GUIDE:\n{style_guide}",
        f"FRAMEWORK SECTION BRIEF:\n{framework_brief}",
        f"MANIFEST (citable as [N]):\n{manifest.as_prompt_list()}",
        f"SYNTHESIS HOOKS FROM BODY SECTIONS:\n{synthesis_hooks_bundle}",
        f"FACTS FOR THIS SECTION:\n{_format_facts_slice(facts_slice)}",
        f"Word target: {word_target}",
        _OUTPUT_FORMAT_REMINDER,
    ])
