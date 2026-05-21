"""Tests for the v2.2 capability manifest loader."""

from __future__ import annotations

from openlia.llm.runtime.report_v2.capability_manifest import (
    CapabilityManifest,
    clear_manifest_cache,
    load_manifest,
)


def test_load_manifest_returns_typed_object():
    clear_manifest_cache()
    m = load_manifest()
    assert isinstance(m, CapabilityManifest)
    assert m.engine_version == "2.2"
    assert isinstance(m.supported, list)
    assert isinstance(m.unsupported, list)


def test_extra_passes_is_an_unsupported_capability():
    clear_manifest_cache()
    m = load_manifest()
    ids = {u.id for u in m.unsupported}
    assert "extra_passes" in ids


def test_unsupported_capability_carries_detection_data():
    clear_manifest_cache()
    m = load_manifest()
    extras = next(u for u in m.unsupported if u.id == "extra_passes")
    assert extras.detect_in_prompt
    assert extras.detect_in_template_keys
    assert extras.user_message
    assert extras.planned_in == "2.3"


def test_known_template_keys_includes_core_fields():
    clear_manifest_cache()
    m = load_manifest()
    for k in (
        "template_id",
        "template_name",
        "department",
        "report_type",
        "engine_version_compat",
        "composer_inputs",
        "required_artifacts",
        "sections",
        "verifier_severity_overrides",
    ):
        assert k in m.known_template_keys


def test_dev_mode_default_is_true():
    clear_manifest_cache()
    m = load_manifest()
    assert m.dev_mode is True


def test_cache_config_loaded_with_transcripts_and_investor_day():
    clear_manifest_cache()
    m = load_manifest()
    assert m.cache.enabled is True
    assert m.cache.transcripts.enabled is True
    assert m.cache.investor_day.enabled is True


def test_unsupported_by_template_key_maps_reserved_keys_to_capability():
    clear_manifest_cache()
    m = load_manifest()
    mapping = m.unsupported_by_template_key()
    assert mapping["extra_passes"].id == "extra_passes"
    assert mapping["loops"].id == "review_loops"
    assert mapping["custom_subagents"].id == "custom_subagents"
