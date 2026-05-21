"""Template loader for v2.2.

Accepts JSON or YAML. Strips reserved keys per the capability manifest and
emits a TemplateLoadNotice per stripped key. Emits an unknown_key notice for
any frontmatter key outside the manifest's known_template_keys allowlist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

import yaml

from openlia.llm.runtime.report_v2.capability_manifest import load_manifest
from openlia.llm.runtime.report_v2.template_v2.spec import TemplateSpecV2

NoticeKind = Literal["reserved_key", "unknown_key"]


@dataclass(frozen=True)
class TemplateLoadNotice:
    kind: NoticeKind
    key: str
    message: str


def load_template_v2(
    raw: str,
    fmt: Literal["yaml", "json"],
) -> tuple[TemplateSpecV2, list[TemplateLoadNotice]]:
    if fmt == "yaml":
        data = yaml.safe_load(raw)
    elif fmt == "json":
        data = json.loads(raw)
    else:
        raise ValueError(f"unsupported fmt: {fmt!r}")
    if not isinstance(data, dict):
        raise ValueError("template root must be a mapping")

    manifest = load_manifest()
    reserved_map = manifest.unsupported_by_template_key()
    known = set(manifest.known_template_keys)

    notices: list[TemplateLoadNotice] = []
    cleaned: dict = {}
    for k, v in data.items():
        if k in reserved_map:
            cap = reserved_map[k]
            notices.append(
                TemplateLoadNotice(
                    kind="reserved_key",
                    key=k,
                    message=cap.user_message.strip(),
                )
            )
            continue
        if k not in known:
            notices.append(
                TemplateLoadNotice(
                    kind="unknown_key",
                    key=k,
                    message=(f"Unknown template key {k!r} ignored. Allowed keys: {sorted(known)}"),
                )
            )
            continue
        cleaned[k] = v

    spec = TemplateSpecV2.model_validate(cleaned)
    return spec, notices
