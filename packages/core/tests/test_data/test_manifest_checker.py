from openlia.data.manifest import RequirementsManifest
from openlia.data.manifest.checker import (
    UnmetRequirement,
    unmet_basic_requirements,
)
from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementTier,
)


def _manifest() -> RequirementsManifest:
    return RequirementsManifest(
        departments=(
            DepartmentManifest(
                department="alpha",
                requirements=(
                    Requirement(
                        type="q",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                    Requirement(
                        type="n",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                    Requirement(
                        type="a",
                        description="d",
                        tier=RequirementTier.ADVANCED,
                    ),
                ),
            ),
            DepartmentManifest(
                department="beta",
                requirements=(
                    Requirement(
                        type="q",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                ),
            ),
        )
    )


def test_all_basic_satisfied_returns_empty_list() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities={"q", "n"},
    )
    assert unmet == []


def test_missing_one_basic_flagged_for_alpha_only() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities={"q"},  # missing 'n'
    )
    assert len(unmet) == 1
    u = unmet[0]
    assert isinstance(u, UnmetRequirement)
    assert u.department == "alpha"
    assert u.requirement_type == "n"


def test_missing_basic_for_multiple_departments() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities=set(),
    )
    pairs = {(u.department, u.requirement_type) for u in unmet}
    assert pairs == {("alpha", "q"), ("alpha", "n"), ("beta", "q")}


def test_advanced_never_flagged() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities={"q", "n"},  # missing 'a' which is advanced
    )
    assert all(u.requirement_type != "a" for u in unmet)


def test_empty_department_is_silently_satisfied() -> None:
    m = RequirementsManifest(departments=(DepartmentManifest(department="empty", requirements=()),))
    assert unmet_basic_requirements(manifest=m, active_capabilities=set()) == []
