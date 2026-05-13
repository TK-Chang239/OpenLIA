"""Per-department YAML prompt loader.

Each department has `<department_id>.yaml` under a prompts root. Leaf
string values are Jinja2 templates — shared snippets live under
`shared/*.yaml.j2` and are available via `{% include %}`.

Slot paths are dot-joined nested-dict keys, e.g. `"chat.system"` or
`"report.stock_initiation.user"`. `PromptSlotNotFound` is raised both
when the YAML file is missing and when the slot doesn't resolve to a
string.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from openlia.prompts import DEPARTMENT_LABELS


class PromptSlotNotFound(Exception):
    """Raised when a requested (department_id, slot) does not resolve."""


def _default_prompts_root() -> Path:
    """Resolve the `openlia.prompts` package directory as a filesystem Path."""
    root = resources.files("openlia.prompts")
    return Path(str(root))


class PromptLoader:
    """Loads and renders prompt slots for a department.

    Construct once per process (or once per test). YAML parse results are
    cached in-memory; edits on disk after first access are invisible.
    """

    def __init__(self, *, root: Path | None = None) -> None:
        self._root = root if root is not None else _default_prompts_root()
        self._env = Environment(
            loader=FileSystemLoader(str(self._root)),
            autoescape=select_autoescape(
                enabled_extensions=(),
                default=False,
            ),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, department_id: str) -> dict[str, Any]:
        if department_id in self._cache:
            return self._cache[department_id]
        path = self._root / f"{department_id}.yaml"
        if not path.exists():
            raise PromptSlotNotFound(
                f"Prompt file not found for department '{department_id}': {path}"
            )
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            raise PromptSlotNotFound(
                f"Prompt file for '{department_id}' must be a mapping, got {type(data).__name__}"
            )
        self._cache[department_id] = data
        return data

    def _resolve_slot(self, data: dict[str, Any], slot: str) -> str:
        node: Any = data
        for part in slot.split("."):
            if not isinstance(node, dict) or part not in node:
                raise PromptSlotNotFound(slot)
            node = node[part]
        if not isinstance(node, str):
            raise PromptSlotNotFound(
                f"Slot '{slot}' resolved to {type(node).__name__}, expected str"
            )
        return node

    def render(self, department_id: str, slot: str, **context: Any) -> str:
        """Render a slot with the provided context. Raises PromptSlotNotFound.

        The `current_desk` template variable is auto-injected from
        `DEPARTMENT_LABELS` if not supplied by the caller. Unknown department
        ids fall through to the raw id so the prompt stays well-formed.
        """
        try:
            data = self._load(department_id)
            template_src = self._resolve_slot(data, slot)
        except PromptSlotNotFound as exc:
            raise PromptSlotNotFound(f"{department_id}:{slot} — {exc}") from None
        merged = {
            "current_desk": DEPARTMENT_LABELS.get(department_id, department_id),
            "skills_menu": [],  # default; callers override
            "response_length": None,  # default; callers override per-session
            "memory_block": None,  # default; slice-13 graph memory hook overrides
            "selected_exemplars": [],  # default; fix-chats exemplar_selector overrides
            "market_basket": None,  # default; fix-chats user_prefs.get_market_basket overrides
            **context,
        }
        template = self._env.from_string(template_src)
        return template.render(**merged)

    def validate_department_slots(self, department_id: str, *, expected: list[str]) -> None:
        """Startup-time check: every expected slot exists. Raises on the first miss."""
        data = self._load(department_id)
        for slot in expected:
            self._resolve_slot(data, slot)
