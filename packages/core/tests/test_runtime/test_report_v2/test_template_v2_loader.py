"""Tests for the v2.2 template loader (JSON + YAML, reserved-key + unknown-key notices)."""

from __future__ import annotations

import json

import pytest
import yaml
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import (
    TemplateLoadNotice,
    load_template_v2,
)

YAML_OK = """
template_id: test_t1
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
composer_inputs:
  - name: ticker
    type: ticker
    label: Ticker
    required: true
required_artifacts: []
sections:
  - id: intro
    name: Intro
    directive: "Write an intro"
"""

YAML_RESERVED = (
    YAML_OK
    + """
extra_passes:
  - name: extra_check
loops:
  - name: review_loop
"""
)

YAML_UNKNOWN = (
    YAML_OK
    + """
mystery_field: hello
"""
)


def test_load_yaml_basic():
    spec, notices = load_template_v2(YAML_OK, fmt="yaml")
    assert spec.template_id == "test_t1"
    assert spec.report_type == "equity_research"
    assert notices == []


def test_load_json_equivalent():
    data = yaml.safe_load(YAML_OK)
    spec, _ = load_template_v2(json.dumps(data), fmt="json")
    assert spec.template_id == "test_t1"


def test_reserved_keys_stripped_with_notices():
    _, notices = load_template_v2(YAML_RESERVED, fmt="yaml")
    notice_keys = {n.key for n in notices if n.kind == "reserved_key"}
    assert "extra_passes" in notice_keys
    assert "loops" in notice_keys


def test_unknown_keys_emit_warning_notice():
    _, notices = load_template_v2(YAML_UNKNOWN, fmt="yaml")
    assert any(n.kind == "unknown_key" and n.key == "mystery_field" for n in notices)


def test_report_type_is_singular_string():
    bad = YAML_OK.replace(
        "report_type: equity_research",
        "report_type:\n  - equity_research\n  - other",
    )
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        load_template_v2(bad, fmt="yaml")


def test_notice_is_frozen_dataclass():
    from dataclasses import FrozenInstanceError

    _, notices = load_template_v2(YAML_RESERVED, fmt="yaml")
    assert all(isinstance(n, TemplateLoadNotice) for n in notices)
    with pytest.raises(FrozenInstanceError):
        notices[0].kind = "unknown_key"  # type: ignore[misc]


def test_invalid_fmt_raises():
    with pytest.raises(ValueError):
        load_template_v2("{}", fmt="xml")  # type: ignore[arg-type]


def test_non_mapping_root_raises():
    with pytest.raises(ValueError, match="mapping"):
        load_template_v2("- foo\n- bar", fmt="yaml")


def test_section_with_trigger_when_loads():
    src = (
        YAML_OK
        + """
  - id: peer_comparison
    name: Peer Comparison
    directive: "Compare peers"
    depends_on: [intro]
    trigger_when: "user provided peer tickers"
"""
    )
    spec, _ = load_template_v2(src, fmt="yaml")
    peer = next(s for s in spec.sections if s.id == "peer_comparison")
    assert peer.trigger_when == "user provided peer tickers"
    assert peer.depends_on == ["intro"]


def test_conversion_prompt_includes_reserved_keys():
    from openlia.llm.runtime.report_v2.template_v2.conversion_prompt import (
        build_conversion_prompt,
    )

    p = build_conversion_prompt()
    assert "extra_passes" in p
    assert "loops" in p
    assert "custom_subagents" in p
    assert "2.2" in p
