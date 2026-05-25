"""Compile a ``ParsedTemplate`` into a v2.3 ``TemplateSpec`` dict.

The parser (``template_parser.py``, pre-existing) splits markdown into a
preamble + per-section list with optional YAML frontmatter blocks.
This service maps that shape onto the v2.3 ``TemplateSpec`` schema
(`packages/core/src/openlia/llm/runtime/report_v2_3/templates/spec.py`).
The returned dict is JSON-serialisable and ready for
``ReportTemplate.template_spec_json`` storage; callers should validate
it via ``TemplateSpec.model_validate`` before persisting so bad shapes
surface to the user immediately.

Mapping:
- ``ParsedSection.id`` → ``SectionSpec.id`` (slug; already validated by parser)
- ``ParsedSection.title`` → ``SectionSpec.title``
- ``ParsedSection.brief`` → ``SectionSpec.intent`` (with title-based fallback)
- ``ParsedSection.frontmatter["methodology_hints"]`` → ``SectionSpec.methodology_hints``
- ``document_frontmatter["name"]`` → ``TemplateSpec.name`` (else ``fallback_name``)
- ``document_frontmatter["shape_description"]`` → ``TemplateSpec.shape_description``
  (else a generated fallback so the required field is populated)
- ``document_frontmatter["ticker_anchored"]`` → ``TemplateSpec.ticker_anchored``
- ``document_frontmatter["default_length"]`` → ``TemplateSpec.default_length``
- ``TemplateSpec.template_id`` is generated from a sanitized name + a short uuid

LLM-driven conversion is intentionally not used — the parser is
deterministic, the schema is permissive enough that most reasonable
markdown structures map cleanly, and round-tripping the original
markdown stays trivially possible.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from openlia_server.services.template_parser import ParsedTemplate

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("_", text.lower()).strip("_")
    return s or "template"


def _build_template_id(name: str) -> str:
    """Generate a stable-looking but unique template_id from the name.

    Format: ``<slug>_<8-char-suffix>`` — passes TemplateSpec's slug regex
    and guarantees uniqueness for the row even when two templates share
    a display name.
    """
    return f"{_slugify(name)}_{uuid.uuid4().hex[:8]}"


def _section_intent(brief: str, title: str) -> str:
    if brief.strip():
        return brief.strip()
    return f"Cover {title}."


def _section_methodology_hints(frontmatter: dict[str, Any]) -> list[str]:
    raw = frontmatter.get("methodology_hints")
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return []


def compile_v23_spec(
    parsed: ParsedTemplate,
    *,
    fallback_name: str,
) -> dict[str, Any]:
    """Return a v2.3 ``TemplateSpec``-shaped dict from a parsed markdown
    template. Raises ``ValueError`` when the parse yielded no sections —
    ``TemplateSpec.sections`` requires ``min_length=1``."""
    if not parsed.sections:
        raise ValueError("Template needs at least one section (use H1 or H2 headings).")
    doc_fm = parsed.document_frontmatter or {}
    name = str(doc_fm.get("name") or fallback_name)
    sections = [
        {
            "id": s.id,
            "title": s.title,
            "intent": _section_intent(s.brief, s.title),
            "methodology_hints": _section_methodology_hints(s.frontmatter),
        }
        for s in parsed.sections
    ]
    out: dict[str, Any] = {
        "template_id": _build_template_id(name),
        "name": name,
        "shape_description": str(doc_fm.get("shape_description") or f"Custom template: {name}."),
        "ticker_anchored": bool(doc_fm.get("ticker_anchored", True)),
        "sections": sections,
    }
    if "default_length" in doc_fm:
        out["default_length"] = str(doc_fm["default_length"])
    return out
