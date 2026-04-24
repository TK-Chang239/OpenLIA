from __future__ import annotations

import json
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

_PACKAGE = "openlia.reports.frameworks"


class FrameworkNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class CustomizationOptions:
    disabled_section_ids: frozenset[str] = field(default_factory=frozenset)
    section_order: tuple[str, ...] | list[str] | None = None
    custom_sections: tuple[dict[str, Any], ...] | list[dict[str, Any]] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class CustomSection:
    id: str
    title: str
    description: str | None


def _read_resource(relative_name: str) -> str:
    try:
        return resources.files(_PACKAGE).joinpath(relative_name).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FrameworkNotFoundError(str(exc)) from exc


def load_framework(
    name: str,
    *,
    customizations: CustomizationOptions | None = None,
) -> dict[str, Any]:
    raw = _read_resource(f"{name}.json")
    data = json.loads(raw)
    if customizations is None:
        return data
    sections = list(data.get("sections", []))
    if customizations.disabled_section_ids:
        sections = [s for s in sections if s.get("id") not in customizations.disabled_section_ids]
    if customizations.section_order:
        order = list(customizations.section_order)
        by_id = {s.get("id"): s for s in sections}
        sections = [deepcopy(by_id[i]) for i in order if i in by_id]
    for extra in customizations.custom_sections:
        sections.append(deepcopy(extra))
    data["sections"] = sections
    return data


def load_framework_customized(
    name: str,
    *,
    enabled_section_ids: set[str],
    custom_sections: Iterable[CustomSection],
) -> dict[str, Any]:
    data = deepcopy(load_framework(name))
    original_sections = list(data.get("sections", []))
    known_ids = {s.get("id") for s in original_sections}
    unknown = set(enabled_section_ids) - known_ids
    if unknown:
        raise ValueError(f"unknown section ids: {sorted(unknown)}")
    kept = [s for s in original_sections if s.get("id") in enabled_section_ids]
    for extra in custom_sections:
        kept.append(
            {
                "id": extra.id,
                "title": extra.title,
                "instructions": extra.description or "",
                "blocks": [],
            }
        )
    data["sections"] = kept
    return data


def load_style_guide(name: str) -> str:
    return _read_resource(f"{name}_style_guide.md")
