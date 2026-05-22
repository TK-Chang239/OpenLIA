"""ArtifactTypeRegistry loading and DAG validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from openlia.llm.runtime.report_v2_2.artifact_types import ArtifactTypeRegistry, _registry
from openlia.llm.runtime.report_v2_2.enums import Fidelity


def test_registry_loads_from_yaml() -> None:
    types = _registry.list_all()
    assert len(types) > 0, "Registry loaded no artifact types"


def test_all_seed_types_present() -> None:
    """All 4 Stage-7a core types and 7 existing helper types must be in the seed."""
    expected = {
        # Stage-7a core
        "section_plan",
        "materialized_section",
        "fidelity_hint",
        "rendered_artifact",
        # existing helpers
        "dcf_valuation_output",
        "chart_artifact",
        "ratio_panel",
        "saas_metrics_output",
        "budget_variance_output",
        "business_investment_output",
        "forecast_output",
    }
    names = {at.name for at in _registry.list_all()}
    missing = expected - names
    assert not missing, f"Seed types missing from registry: {missing}"


def test_get_existing_type() -> None:
    at = _registry.get("dcf_valuation_output")
    assert at is not None
    assert at.name == "dcf_valuation_output"


def test_get_missing_type_returns_none() -> None:
    assert _registry.get("nonexistent_artifact_xyz") is None


def test_all_types_have_three_fidelity_levels() -> None:
    for at in _registry.list_all():
        for level in Fidelity:
            assert level in at.fidelity, (
                f"ArtifactType {at.name!r} missing fidelity level {level.value!r}"
            )


def test_validate_dag_passes_on_seed() -> None:
    # Should not raise — the seed YAML has no cycles.
    _registry.validate_dag()


def test_validate_dag_detects_cycle(tmp_path: Path) -> None:
    """Construct a synthetic cyclic config and assert validate_dag raises with cycle path."""
    cyclic_yaml = {
        "artifact_types": [
            {
                "name": "a",
                "fidelity": {"headline": "h", "summary": "s", "full": "f"},
                "depends_on": ["b"],
            },
            {
                "name": "b",
                "fidelity": {"headline": "h", "summary": "s", "full": "f"},
                "depends_on": ["c"],
            },
            {
                "name": "c",
                "fidelity": {"headline": "h", "summary": "s", "full": "f"},
                "depends_on": ["a"],  # cycle: a -> b -> c -> a
            },
        ]
    }
    yaml_file = tmp_path / "cyclic.yaml"
    yaml_file.write_text(yaml.dump(cyclic_yaml))

    registry = ArtifactTypeRegistry(path=yaml_file)
    with pytest.raises(ValueError) as exc_info:
        registry.validate_dag()

    msg = str(exc_info.value)
    # Cycle path must appear in the error message.
    assert "Cycle detected" in msg
    # At least two of the three nodes must appear.
    nodes_mentioned = sum(1 for n in ("a", "b", "c") if n in msg)
    assert nodes_mentioned >= 2, f"Cycle path not surfaced in error: {msg}"


def test_validate_dag_detects_missing_dependency(tmp_path: Path) -> None:
    """depends_on referencing a non-existent type raises at validation time."""
    broken_yaml = {
        "artifact_types": [
            {
                "name": "orphan",
                "fidelity": {"headline": "h", "summary": "s", "full": "f"},
                "depends_on": ["ghost_type"],
            },
        ]
    }
    yaml_file = tmp_path / "broken.yaml"
    yaml_file.write_text(yaml.dump(broken_yaml))

    registry = ArtifactTypeRegistry(path=yaml_file)
    with pytest.raises(ValueError, match="ghost_type"):
        registry.validate_dag()


def test_duplicate_artifact_type_raises(tmp_path: Path) -> None:
    dup_yaml = {
        "artifact_types": [
            {
                "name": "dup",
                "fidelity": {"headline": "h", "summary": "s", "full": "f"},
                "depends_on": [],
            },
            {
                "name": "dup",
                "fidelity": {"headline": "h", "summary": "s", "full": "f"},
                "depends_on": [],
            },
        ]
    }
    yaml_file = tmp_path / "dup.yaml"
    yaml_file.write_text(yaml.dump(dup_yaml))

    with pytest.raises(ValueError, match="Duplicate"):
        ArtifactTypeRegistry(path=yaml_file)


def test_invalid_fidelity_level_raises(tmp_path: Path) -> None:
    bad_yaml = {
        "artifact_types": [
            {
                "name": "bad",
                "fidelity": {"headline": "h", "bogus_level": "x", "full": "f"},
                "depends_on": [],
            },
        ]
    }
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text(yaml.dump(bad_yaml))

    with pytest.raises(ValueError, match="bogus_level"):
        ArtifactTypeRegistry(path=yaml_file)
