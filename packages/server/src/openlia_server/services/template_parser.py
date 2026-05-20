"""Mechanical template-markdown parser (PR 11).

Splits ingested markdown into a `ParsedTemplate` (preamble + sections).
Section boundaries are H1/H2 headings; the first segment before the first
heading becomes `global_preface`. Each section's body may carry an optional
YAML frontmatter block fenced in an HTML comment (`<!-- openlia ... -->`)
that maps onto the SectionSpec optional fields. Document-level frontmatter
sits at the very top of the document, before any heading.

No LLM call is involved — the parser is pure and deterministic. This is
the upload path's load-bearing surface.

**Document-style requirement:** uploaded `.docx` files must use Word's
Heading 1 / Heading 2 styles for section titles (not just bold text on
ordinary paragraphs). Mammoth converts true heading styles into markdown
`#`/`##` lines; bold paragraphs are emitted as `__...__` which the parser
deliberately ignores. The review UI surfaces this when the parser finds
zero sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

# Slug normalization: lowercase, replace runs of non-alphanumeric with `_`.
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Section frontmatter block:  <!-- openlia\n<yaml>\n-->
_FRONTMATTER_RE = re.compile(
    r"<!--\s*openlia\s*\n(?P<body>.*?)\n-->",
    re.DOTALL,
)

# H1/H2 heading boundary (must be at start of a line).
_HEADING_RE = re.compile(r"(?m)^(#{1,2})\s+(.+?)\s*$")


@dataclass(frozen=True)
class ParsedSection:
    id: str
    title: str
    brief: str
    frontmatter: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedTemplate:
    global_preface: str
    document_frontmatter: dict[str, Any]
    sections: tuple[ParsedSection, ...]


def slugify(text: str) -> str:
    s = _SLUG_RE.sub("_", text.lower()).strip("_")
    return s or "section"


def _extract_and_strip_frontmatter(body: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.search(body)
    if m is None:
        return {}, body
    try:
        data = yaml.safe_load(m.group("body")) or {}
        if not isinstance(data, dict):
            data = {}
    except yaml.YAMLError:
        data = {}
    stripped = body[: m.start()] + body[m.end() :]
    return data, stripped.lstrip("\n")


def _disambiguate_duplicates(slugs: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for slug in slugs:
        if slug not in seen:
            seen[slug] = 0
            out.append(slug)
        else:
            seen[slug] += 1
            out.append(f"{slug}_{seen[slug] + 1}")
    return out


def parse_template(markdown: str) -> ParsedTemplate:
    """Split `markdown` into a preamble + per-section list.

    Section boundaries are H1/H2 headings. The first chunk before the first
    heading becomes `global_preface`. Each section's body may carry an
    optional `<!-- openlia ... -->` frontmatter block.
    """
    # Document-level frontmatter: a leading frontmatter block before any heading.
    doc_fm: dict[str, Any] = {}
    first_heading = _HEADING_RE.search(markdown)
    preamble_text = markdown if first_heading is None else markdown[: first_heading.start()]
    doc_fm, preamble = _extract_and_strip_frontmatter(preamble_text)

    if first_heading is None:
        return ParsedTemplate(
            global_preface=preamble.strip(),
            document_frontmatter=doc_fm,
            sections=(),
        )

    # Iterate headings, capture body up to next heading.
    matches = list(_HEADING_RE.finditer(markdown))
    raw_sections = []
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[body_start:body_end].strip()
        raw_sections.append((title, body))

    slugs = _disambiguate_duplicates([slugify(t) for t, _ in raw_sections])
    parsed_sections: list[ParsedSection] = []
    for (title, body), slug in zip(raw_sections, slugs, strict=False):
        fm, brief = _extract_and_strip_frontmatter(body)
        parsed_sections.append(
            ParsedSection(id=slug, title=title, brief=brief.strip(), frontmatter=fm)
        )

    return ParsedTemplate(
        global_preface=preamble.strip(),
        document_frontmatter=doc_fm,
        sections=tuple(parsed_sections),
    )
