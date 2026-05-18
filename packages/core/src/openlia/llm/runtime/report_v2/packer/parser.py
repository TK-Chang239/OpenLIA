"""Parse a section Markdown file into frontmatter + ordered segments."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_FENCE_RE = re.compile(r"^```([\w:]+)\n(.*?)\n```", re.DOTALL | re.MULTILINE)
_CITATION_RE = re.compile(r"\[(\d+)\]")
_FM_LINE_RE = re.compile(r"^(\s*[a-z_][a-z0-9_]*\s*:)\s+(.+?)\s*$", re.IGNORECASE)


@dataclass
class TextSegment:
    text: str
    citation_ids: list[int] = field(default_factory=list)


@dataclass
class FencedBlockSegment:
    block_type: str
    data: dict[str, Any]


Segment = TextSegment | FencedBlockSegment


@dataclass
class ParsedSection:
    frontmatter: dict[str, Any]
    segments: list[Segment]


def _autoquote_frontmatter(fm_text: str) -> str:
    """Auto-quote unquoted scalar values containing colons before YAML parsing."""
    out_lines = []
    for line in fm_text.split("\n"):
        m = _FM_LINE_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        key, value = m.group(1), m.group(2)
        # Skip already-quoted values, collections, booleans, numbers, or empty.
        if (
            not value
            or value[0] in ("'", '"', "[", "{")
            or value.lower()
            in (
                "true",
                "false",
                "null",
                "~",
            )
        ):
            out_lines.append(line)
            continue
        # Auto-quote if the value contains a colon-space sequence or a trailing colon.
        if ": " in value or value.endswith(":"):
            safe = value.replace('"', '\\"')
            out_lines.append(f'{key} "{safe}"')
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def _normalize(content: str) -> str:
    # Normalize line endings.
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Strip leading whitespace.
    content = content.lstrip()
    # Strip markdown code-fence wrapping.
    fence_match = re.match(r"^```(?:markdown|md)?\s*\n(.*?)\n```\s*$", content, re.DOTALL)
    if fence_match:
        content = fence_match.group(1)
    # Strip leading prose preamble (anything before the first `---` line).
    # Only do this if a closing `---` also exists — i.e. a valid YAML block follows.
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "---":
                    return "\n".join(lines[i:])
            break  # No closing `---`; leave content as-is and let regex fail.
    return content


def parse_section_file(content: str) -> ParsedSection:
    content = _normalize(content)
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        raise ValueError("missing or malformed frontmatter")

    fm_text = _autoquote_frontmatter(fm_match.group(1))
    try:
        frontmatter = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"frontmatter YAML invalid: {e}") from e
    body = fm_match.group(2)

    segments: list[Segment] = []
    cursor = 0
    block_index = 0
    for m in _FENCE_RE.finditer(body):
        if m.start() > cursor:
            text = body[cursor : m.start()].strip()
            if text:
                segments.append(_text_segment(text))
        block_type = m.group(1)
        raw = m.group(2)
        try:
            data = yaml.safe_load(raw) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"block {block_index} ({block_type}): malformed YAML: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"block {block_index} ({block_type}): YAML must be a mapping")
        segments.append(FencedBlockSegment(block_type=block_type, data=data))
        cursor = m.end()
        block_index += 1
    if cursor < len(body):
        tail = body[cursor:].strip()
        if tail:
            segments.append(_text_segment(tail))

    return ParsedSection(frontmatter=frontmatter, segments=segments)


def _text_segment(text: str) -> TextSegment:
    ids = [int(x) for x in _CITATION_RE.findall(text)]
    return TextSegment(text=text, citation_ids=ids)
