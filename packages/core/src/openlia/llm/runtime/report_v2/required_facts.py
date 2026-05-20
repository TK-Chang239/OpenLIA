"""Required-facts gate for sections that declare hard dependencies (PR 15).

When a `SectionSpec` lists `required_facts`, the runner consults this helper
before dispatch. Missing facts cause the section to short-circuit into a
`SectionResult` with state `SKIPPED_REQUIRED_FACTS`; the assembler then
renders an admonition banner naming the missing facts in place of the
section body. The rest of the report continues to render.

The check is name-based: a `Fact` is "available" if its `name` appears in the
provided iterable. The fact's actual value is ignored — None values still count
as present (the section will surface its own None handling). This matches the
plan §12 Q4 contract: "missing required fact → skip with banner".
"""

from __future__ import annotations

from collections.abc import Iterable

from openlia.reports.frameworks.template_spec import SectionSpec


def missing_required_facts(
    section: SectionSpec,
    available_fact_names: Iterable[str],
) -> tuple[str, ...]:
    """Return the names of `section.required_facts` not present in availability set.

    Returns an empty tuple when the section declares no required_facts (the
    section will dispatch unconditionally). Always returns a stable order
    matching the declaration order in the SectionSpec.
    """
    if not section.required_facts:
        return ()
    available = set(available_fact_names)
    return tuple(name for name in section.required_facts if name not in available)
