"""Department health derivation (pure).

Spec §10.

A department is `active` iff every `required_categories` has at least one
`validated` connector with matching `category` and every `required_any_of`
group has at least one validated member.

Otherwise the department is `disabled` with a structured `reason` string
listing missing categories and/or unsatisfied any-of groups.

This module is pure — no DB session, no FastAPI, no global state. The
caller passes in the validated connectors as a plain sequence. Connectors
may be ORM rows or dataclasses; the function only reads the duck-typed
attributes documented below.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from openlia.connectors.types import Category, ConnectorStatus
from openlia.departments.base import Department

DepartmentStatus = Literal["active", "disabled"]


class _ValidatedConnectorLike(Protocol):
    """Duck-type for the connector rows / dataclasses passed into the check.

    Only `category` and `status` are read. Both are read as values
    coercible to `Category` / `ConnectorStatus`.
    """

    category: Any  # str or Category
    status: Any  # str or ConnectorStatus


@dataclass(frozen=True)
class DepartmentHealth:
    department_id: str
    status: DepartmentStatus
    reason: str | None
    missing_categories: list[Category]
    unsatisfied_any_of: list[tuple[Category, ...]] = field(default_factory=list)
    satisfied_categories: list[Category] = field(default_factory=list)


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
) -> DepartmentHealth:
    """Derive a `DepartmentHealth` for `dept`.

    `validated_connectors` should be the full connector inventory; this
    function filters to `status == validated` itself so the caller can
    pass the unfiltered list.
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

    # Validated categories relevant to this department (required, optional, or in
    # an any-of group) — the dept's own coverage, not the whole system's.
    relevant_categories = (
        set(dept.required_categories)
        | set(getattr(dept, "optional_categories", ()))
        | {c for group in any_of_groups for c in group}
    )
    satisfied_categories = sorted(validated_cats & relevant_categories)

    if not missing_categories and not unsatisfied_any_of:
        return DepartmentHealth(
            department_id=department_id,
            status="active",
            reason=None,
            missing_categories=[],
            unsatisfied_any_of=[],
            satisfied_categories=satisfied_categories,
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
    reason = "; ".join(parts)

    return DepartmentHealth(
        department_id=department_id,
        status="disabled",
        reason=reason,
        missing_categories=missing_categories,
        unsatisfied_any_of=unsatisfied_any_of,
        satisfied_categories=satisfied_categories,
    )


__all__ = ["DepartmentHealth", "DepartmentStatus", "check_dept_health"]
