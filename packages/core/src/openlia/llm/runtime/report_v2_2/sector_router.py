"""GICS-based sector routing for the v2.2 equity research engine.

Loads sector_routing.yaml (in openlia/data/reference/) and maps a
6-digit GICS sub-industry code to the appropriate sector module template.

Per spec §3.  Single public function: route_to_sector_template().
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Navigate from this file up to the openlia package root, then into data/reference/.
# Avoids relying on importlib.resources for a directory that has no __init__.py.
_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent  # openlia/
_ROUTING_YAML_PATH = _PACKAGE_ROOT / "data" / "reference" / "sector_routing.yaml"

_DEFAULT_TEMPLATE = "stock_initiation_v2"


@lru_cache(maxsize=1)
def _load_routing() -> dict[str, object]:
    """Load and cache the sector_routing.yaml.  Cached after first call."""
    if not _ROUTING_YAML_PATH.exists():
        logger.warning(
            "sector_routing.yaml not found at %s; all codes will route to default template.",
            _ROUTING_YAML_PATH,
        )
        return {}
    data = yaml.safe_load(_ROUTING_YAML_PATH.read_text()) or {}
    return data  # type: ignore[return-value]


def _build_code_map(routing_data: dict[str, object]) -> dict[str, str]:
    """Build a flat {gics_code: template_name} map from the routing YAML."""
    code_map: dict[str, str] = {}
    gics_routing = routing_data.get("gics_routing", {})
    if not isinstance(gics_routing, dict):
        return code_map
    for _sector_key, sector_cfg in gics_routing.items():
        if not isinstance(sector_cfg, dict):
            continue
        template_name = sector_cfg.get("template", "")
        gics_codes = sector_cfg.get("gics_codes", [])
        if not isinstance(gics_codes, list):
            continue
        for code in gics_codes:
            # Strip inline comments after #
            raw = str(code).strip()
            if not template_name:
                continue
            code_map[raw] = template_name
    return code_map


@lru_cache(maxsize=1)
def _get_code_map() -> dict[str, str]:
    return _build_code_map(_load_routing())


def route_to_sector_template(gics_code: str | None) -> str:
    """Return the template name for the given GICS sub-industry code.

    Falls back to ``default_template`` (stock_initiation_v2) for unknown or
    None codes.  Matching is exact on the 6-digit code string.

    Args:
        gics_code: 6-digit GICS sub-industry code as a string, e.g. "401010".
                   Pass None or an empty string for unknown/unclassified.

    Returns:
        Template name string, e.g. "banks_v2_2" or "stock_initiation_v2".
    """
    if not gics_code:
        return _default_template_name()

    code_map = _get_code_map()
    template = code_map.get(gics_code.strip())
    if template:
        return template

    logger.debug(
        "GICS code %r not matched in sector_routing.yaml; routing to default template.",
        gics_code,
    )
    return _default_template_name()


def _default_template_name() -> str:
    """Return the configured default template, or the hardcoded fallback."""
    routing_data = _load_routing()
    default = routing_data.get("default_template", _DEFAULT_TEMPLATE)
    return str(default)


def clear_routing_cache() -> None:
    """Invalidate the in-process routing cache.  Useful in tests that patch the YAML."""
    _load_routing.cache_clear()
    _get_code_map.cache_clear()
