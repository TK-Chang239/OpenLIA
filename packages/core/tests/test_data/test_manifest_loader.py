import pytest
from openlia.data.manifest.loader import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    load_manifest_from_path,
)
from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)


def test_requirement_tier_enum() -> None:
    assert RequirementTier.BASIC.value == "basic"
    assert RequirementTier.ADVANCED.value == "advanced"


def test_requirement_round_trip() -> None:
    r = Requirement(
        type="stock_quote",
        description="Real-time or delayed stock price.",
        tier=RequirementTier.BASIC,
    )
    assert r.type == "stock_quote"
    assert r.tier is RequirementTier.BASIC


def test_department_manifest_basic_and_advanced_views() -> None:
    dm = DepartmentManifest(
        department="equity_research",
        requirements=[
            Requirement(type="stock_quote", description="d1", tier=RequirementTier.BASIC),
            Requirement(type="stock_grade", description="d2", tier=RequirementTier.ADVANCED),
            Requirement(type="company_news", description="d3", tier=RequirementTier.BASIC),
        ],
    )
    assert {r.type for r in dm.basic()} == {"stock_quote", "company_news"}
    assert {r.type for r in dm.advanced()} == {"stock_grade"}


def test_requirements_manifest_lookup() -> None:
    manifest = RequirementsManifest(
        departments=[
            DepartmentManifest(
                department="equity_research",
                requirements=[
                    Requirement(
                        type="stock_quote",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                ],
            ),
        ],
    )
    assert manifest.department("equity_research").department == "equity_research"
    assert manifest.department("unknown") is None


def test_default_manifest_loads() -> None:
    manifest = load_manifest()
    assert manifest.department("equity_research") is not None


def test_default_manifest_equity_research_has_expected_basics() -> None:
    manifest = load_manifest()
    er = manifest.department("equity_research")
    assert er is not None
    basic_types = {r.type for r in er.basic()}
    assert {"stock_quote", "historical_prices", "company_news"} <= basic_types


def test_default_manifest_path_points_into_package() -> None:
    assert DEFAULT_MANIFEST_PATH.exists()
    assert DEFAULT_MANIFEST_PATH.name == "requirements.yaml"


def test_load_from_arbitrary_path(tmp_path: pytest.TempPathFactory) -> None:
    yaml_text = """
departments:
  - department: test_dept
    requirements:
      - type: foo
        description: foo data
        tier: basic
      - type: bar
        description: bar data
        tier: advanced
"""
    p = tmp_path / "m.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    m = load_manifest_from_path(p)
    td = m.department("test_dept")
    assert td is not None
    assert {r.type for r in td.basic()} == {"foo"}
    assert {r.type for r in td.advanced()} == {"bar"}


def test_load_missing_file_raises(tmp_path: pytest.TempPathFactory) -> None:
    with pytest.raises(FileNotFoundError):
        load_manifest_from_path(tmp_path / "does-not-exist.yaml")


def test_load_invalid_tier_raises(tmp_path: pytest.TempPathFactory) -> None:
    bad = tmp_path / "m.yaml"
    bad.write_text(
        """
departments:
  - department: x
    requirements:
      - type: t
        description: d
        tier: not_a_tier
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_manifest_from_path(bad)
