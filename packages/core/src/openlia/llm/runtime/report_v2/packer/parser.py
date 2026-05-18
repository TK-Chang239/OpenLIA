"""Parse a section Markdown file into frontmatter + ordered segments."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_FENCE_RE = re.compile(r"^```([\w:]+)\n(.*?)\n```", re.DOTALL | re.MULTILINE)
_CITATION_RE = re.compile(r"\[(\d+)\]")


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


def parse_section_file(content: str) -> ParsedSection:
    fm_match = _FRONTMATTER_RE.match(content.lstrip())
    if not fm_match:
        raise ValueError("missing or malformed frontmatter")

    frontmatter = yaml.safe_load(fm_match.group(1)) or {}
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
