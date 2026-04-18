"""Pydantic models for the department data-requirements manifest."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RequirementTier(StrEnum):
    BASIC = "basic"
    ADVANCED = "advanced"


class Requirement(BaseModel):
    """One data need for a department."""

    model_config = ConfigDict(frozen=True)

    type: str
    description: str
    tier: RequirementTier


class DepartmentManifest(BaseModel):
    """All requirements for one department."""

    model_config = ConfigDict(frozen=True)

    department: str
    requirements: tuple[Requirement, ...]

    def __init__(self, **data: object) -> None:
        reqs = data.get("requirements")
        if isinstance(reqs, list):
            data["requirements"] = tuple(reqs)
        super().__init__(**data)

    def basic(self) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if r.tier is RequirementTier.BASIC)

    def advanced(self) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if r.tier is RequirementTier.ADVANCED)


class RequirementsManifest(BaseModel):
    """Root of the manifest — all configured departments."""

    model_config = ConfigDict(frozen=True)

    departments: tuple[DepartmentManifest, ...]

    def __init__(self, **data: object) -> None:
        deps = data.get("departments")
        if isinstance(deps, list):
            data["departments"] = tuple(deps)
        super().__init__(**data)

    def department(self, name: str) -> DepartmentManifest | None:
        for dm in self.departments:
            if dm.department == name:
                return dm
        return None
