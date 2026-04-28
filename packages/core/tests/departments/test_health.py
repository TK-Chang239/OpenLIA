"""Tests for `check_dept_health` (Phase 10 Task 10.1)."""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.types import Category, ConnectorStatus
from openlia.departments import (
    EquityResearchDepartment,
    MacroResearchDepartment,
    RetailSentimentDepartment,
)
from openlia.departments.health import check_dept_health
from openlia.departments.loader import load_needs


@dataclass
class _Conn:
    category: Category | str
    status: ConnectorStatus | str


@dataclass
class _Spec:
    department_id: str
    need_id: str


# ---------------------------------------------------------------------------
# Chat-flow dept (Equity Research) — required: financial; requires_runner=False
# ---------------------------------------------------------------------------


def test_active_when_required_category_validated():
    dept = EquityResearchDepartment()
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"
    assert health.reason is None
    assert health.missing_categories == []
    assert health.unresolved_needs == []
    assert health.department_id == "equity_research"


def test_disabled_when_required_category_missing():
    dept = EquityResearchDepartment()
    health = check_dept_health(dept, validated_connectors=[], runner_specs=[])
    assert health.status == "disabled"
    assert health.missing_categories == [Category.FINANCIAL]
    assert "financial" in health.reason


def test_disabled_when_required_category_only_failed_or_pending():
    dept = EquityResearchDepartment()
    connectors = [
        _Conn(category=Category.FINANCIAL, status=ConnectorStatus.FAILED),
        _Conn(category=Category.FINANCIAL, status=ConnectorStatus.PENDING),
    ]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "disabled"
    assert Category.FINANCIAL in health.missing_categories


def test_optional_category_missing_does_not_disable():
    dept = EquityResearchDepartment()
    # Required category present; optional categories (news, social, web_search) absent.
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"
    assert health.missing_categories == []


def test_string_status_and_category_accepted():
    """ORM rows pass values as strings; coerce them transparently."""
    dept = EquityResearchDepartment()
    connectors = [_Conn(category="financial", status="validated")]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"


# ---------------------------------------------------------------------------
# Runner-bearing dept (Macro Research) — requires_runner=True with declared needs
# ---------------------------------------------------------------------------


def test_runner_dept_disabled_with_unresolved_need():
    dept = MacroResearchDepartment()
    needs = load_needs(dept.name)
    assert needs, "MacroResearch needs.yaml must declare at least one need"

    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    # Resolve all but the first need
    specs = [_Spec(department_id=dept.name, need_id=n.id) for n in needs[1:]]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "disabled"
    assert health.unresolved_needs == [needs[0].id]
    assert needs[0].id in health.reason


def test_runner_dept_active_when_all_needs_resolved():
    dept = MacroResearchDepartment()
    needs = load_needs(dept.name)
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    specs = [_Spec(department_id=dept.name, need_id=n.id) for n in needs]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "active"
    assert health.unresolved_needs == []


def test_runner_dept_specs_for_other_dept_do_not_count():
    dept = MacroResearchDepartment()
    needs = load_needs(dept.name)
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    # Specs reference a different dept — should not satisfy MR needs
    specs = [_Spec(department_id="retail_sentiment", need_id=n.id) for n in needs]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "disabled"
    assert health.unresolved_needs == [n.id for n in needs]


def test_runner_dept_disabled_lists_both_missing_categories_and_unresolved_needs():
    dept = MacroResearchDepartment()
    needs = load_needs(dept.name)
    health = check_dept_health(dept, validated_connectors=[], runner_specs=[])
    assert health.status == "disabled"
    assert Category.FINANCIAL in health.missing_categories
    assert health.unresolved_needs == [n.id for n in needs]
    assert "Missing required categories" in health.reason
    assert "Unresolved needs" in health.reason


# ---------------------------------------------------------------------------
# Chat-flow dept ignores needs entirely (requires_runner=False)
# ---------------------------------------------------------------------------


def test_chat_dept_ignores_needs_yaml_when_requires_runner_false():
    dept = EquityResearchDepartment()
    assert dept.requires_runner is False
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    # No specs at all — chat dept must still be active
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"
    assert health.unresolved_needs == []


def test_runner_dept_rs_active_when_all_required_categories_and_needs_resolved():
    """Retail Sentiment is a runner dept; satisfy all required cats + needs."""
    dept = RetailSentimentDepartment()
    needs = load_needs(dept.name)
    connectors = [
        _Conn(category=cat, status=ConnectorStatus.VALIDATED) for cat in dept.required_categories
    ]
    specs = [_Spec(department_id=dept.name, need_id=n.id) for n in needs]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "active"
