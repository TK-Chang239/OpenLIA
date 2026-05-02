"""Department health derivation (pure).

Spec §10.

A department is `active` iff:
  - every `required_categories` has at least one `validated` connector with
    matching `category`, AND
  - if `requires_runner=True`, every need declared in `<dept>.needs.yaml`
    has a `RunnerCallableSpec` row matching `(department_id, need_id)`.

Otherwise the department is `disabled` with a structured `reason` string
listing missing categories and/or unresolved needs.

This module is pure — no DB session, no FastAPI, no global state. The
caller passes in the validated connectors and runner specs as plain
sequences. Connectors and specs may be ORM rows or dataclasses; the
function only reads the duck-typed attributes documented below.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from openlia.connectors.types import Category, ConnectorStatus
from openlia.departments.base import Department
from openlia.departments.loader import load_needs

DepartmentStatus = Literal["active", "disabled"]


class _ValidatedConnectorLike(Protocol):
    """Duck-type for the connector rows / dataclasses passed into the check.

    Only `category` and `status` are read. Both are read as values
    coercible to `Category` / `ConnectorStatus`.
    """

    category: Any  # str or Category
    status: Any  # str or ConnectorStatus


class _RunnerSpecLike(Protocol):
    """Duck-type for runner-spec rows / dataclasses.

    Only `department_id` and `need_id` are read.
    """

    department_id: str
    need_id: str


@dataclass(frozen=True)
class DepartmentHealth:
    department_id: str
    status: DepartmentStatus
    reason: str | None
    missing_categories: list[Category]
    unresolved_needs: list[str]
    unsatisfied_any_of: list[tuple[Category, ...]] = field(default_factory=list)


def _coerce_category(value: Any) -> Category | None:
    if isinstance(value, Category):
        return value
    try:
        return Category(value)
    except (ValueError, TypeError):
        return None


def _is_validated(value: Any) -> bool:
    if isinstance(value, ConnectorStatus):
        return value is ConnectorStatus.VALIDATED
    return value == ConnectorStatus.VALIDATED.value


def check_dept_health(
    dept: Department,
    *,
    validated_connectors: Sequence[_ValidatedConnectorLike],
    runner_specs: Sequence[_RunnerSpecLike],
) -> DepartmentHealth:
    """Derive a `DepartmentHealth` for `dept`.

    `validated_connectors` should be the full connector inventory; this
    function filters to `status == validated` itself so the caller can
    pass the unfiltered list. `runner_specs` should be the full spec
    inventory; the function filters to specs whose `department_id`
    matches `dept.name`.
    """

    department_id = dept.name

    validated_cats: set[Category] = set()
    for c in validated_connectors:
        if not _is_validated(c.status):
            continue
        cat = _coerce_category(c.category)
        if cat is not None:
            validated_cats.add(cat)

    missing_categories: list[Category] = [
        cat for cat in dept.required_categories if cat not in validated_cats
    ]

    any_of_groups: tuple[tuple[Category, ...], ...] = getattr(dept, "required_any_of", ()) or ()
    unsatisfied_any_of: list[tuple[Category, ...]] = [
        group for group in any_of_groups if not any(c in validated_cats for c in group)
    ]

    unresolved_needs: list[str] = []
    if dept.requires_runner:
        resolved_need_ids: set[str] = {
            spec.need_id for spec in runner_specs if spec.department_id == department_id
        }
        needs = load_needs(department_id)
        for need in needs:
            if need.id not in resolved_need_ids:
                unresolved_needs.append(need.id)

    if not missing_categories and not unresolved_needs and not unsatisfied_any_of:
        return DepartmentHealth(
            department_id=department_id,
            status="active",
            reason=None,
            missing_categories=[],
            unresolved_needs=[],
            unsatisfied_any_of=[],
        )

    parts: list[str] = []
    if missing_categories:
        cat_str = ", ".join(c.value for c in missing_categories)
        parts.append(f"Missing required categories: {cat_str}")
    if unsatisfied_any_of:
        group_strs = [
            "(" + " or ".join(c.value for c in group) + ")" for group in unsatisfied_any_of
        ]
        parts.append("Missing any-of groups: " + ", ".join(group_strs))
    if unresolved_needs:
        need_str = ", ".join(unresolved_needs)
        parts.append(f"Unresolved needs: {need_str}")
    reason = "; ".join(parts)

    return DepartmentHealth(
        department_id=department_id,
        status="disabled",
        reason=reason,
        missing_categories=missing_categories,
        unresolved_needs=unresolved_needs,
        unsatisfied_any_of=unsatisfied_any_of,
    )


__all__ = ["DepartmentHealth", "DepartmentStatus", "check_dept_health"]
