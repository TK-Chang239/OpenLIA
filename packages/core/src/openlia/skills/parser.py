from __future__ import annotations

import yaml
from pydantic import ValidationError

from openlia.skills.types import SkillManifest

_OPEN = "---\n"
_CLOSE = "\n---\n"


def parse_skill_md(text: str) -> tuple[SkillManifest, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith(_OPEN):
        raise ValueError("SKILL.md must start with '---' frontmatter")
    rest = text[len(_OPEN) :]
    end = rest.find(_CLOSE)
    if end == -1:
        raise ValueError("SKILL.md frontmatter not closed with '---'")
    raw = rest[:end]
    body = rest[end + len(_CLOSE) :]
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    if "version" in data and not isinstance(data["version"], str):
        data["version"] = str(data["version"])
    try:
        manifest = SkillManifest(**data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return manifest, body


def serialize_skill_md(manifest: SkillManifest, body: str) -> str:
    fm = manifest.model_dump(exclude_none=True)
    raw = yaml.safe_dump(fm, sort_keys=False).rstrip() + "\n"
    return f"---\n{raw}---\n{body}"
