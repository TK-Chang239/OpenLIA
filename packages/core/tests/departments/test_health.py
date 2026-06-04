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
# Runner-bearing dept (Retail Sentiment) — requires_runner=True with needs
# ---------------------------------------------------------------------------


def test_runner_dept_disabled_with_unresolved_need():
    dept = RetailSentimentDepartment()
    needs = load_needs(dept.name)
    assert needs, "RetailSentiment needs.yaml must declare at least one need"

    connectors = [
        _Conn(category=cat, status=ConnectorStatus.VALIDATED) for cat in dept.required_categories
    ]
    # Resolve all but the first need.
    specs = [_Spec(department_id=dept.name, need_id=n.id) for n in needs[1:]]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "disabled"
    assert health.unresolved_needs == [needs[0].id]
    assert needs[0].id in health.reason


def test_runner_dept_specs_for_other_dept_do_not_count():
    dept = RetailSentimentDepartment()
    needs = load_needs(dept.name)
    connectors = [
        _Conn(category=cat, status=ConnectorStatus.VALIDATED) for cat in dept.required_categories
    ]
    # Specs reference a different dept — must not satisfy RS needs.
    specs = [_Spec(department_id="macro_research", need_id=n.id) for n in needs]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=specs)
    assert health.status == "disabled"
    assert health.unresolved_needs == [n.id for n in needs]


def test_runner_dept_disabled_lists_both_missing_categories_and_unresolved_needs():
    dept = RetailSentimentDepartment()
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


# ---------------------------------------------------------------------------
# required_any_of — at-least-one-of disjunctive category groups
# ---------------------------------------------------------------------------


@dataclass
class _DeptStub:
    """Minimal Department-shaped stub for exercising required_any_of."""

    name: str = "stub_dept"
    required_categories: tuple[Category, ...] = ()
    optional_categories: tuple[Category, ...] = ()
    required_any_of: tuple[tuple[Category, ...], ...] = ()
    requires_runner: bool = False


def test_required_any_of_active_when_one_member_validated():
    dept = _DeptStub(required_any_of=((Category.NEWS, Category.WEB_SEARCH),))
    connectors = [_Conn(category=Category.WEB_SEARCH, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"
    assert health.missing_categories == []


def test_required_any_of_disabled_when_no_member_validated():
    dept = _DeptStub(required_any_of=((Category.NEWS, Category.WEB_SEARCH),))
    health = check_dept_health(dept, validated_connectors=[], runner_specs=[])
    assert health.status == "disabled"
    assert "news" in health.reason
    assert "web_search" in health.reason


def test_required_any_of_disabled_lists_each_unsatisfied_group():
    dept = _DeptStub(
        required_categories=(Category.FINANCIAL,),
        required_any_of=((Category.NEWS, Category.WEB_SEARCH),),
    )
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "disabled"
    # Required-categories satisfied; the missing piece is the disjunctive group.
    assert Category.FINANCIAL not in health.missing_categories
    assert "news" in health.reason and "web_search" in health.reason


def test_required_any_of_unrelated_category_does_not_satisfy():
    dept = _DeptStub(required_any_of=((Category.NEWS, Category.WEB_SEARCH),))
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "disabled"


def test_macro_research_requires_only_web_search():
    dept = MacroResearchDepartment()
    assert dept.required_categories == (Category.WEB_SEARCH,)
    assert Category.FINANCIAL in dept.optional_categories
    assert Category.NEWS in dept.optional_categories
    assert dept.requires_runner is False


def test_macro_research_active_with_web_search_only():
    dept = MacroResearchDepartment()
    connectors = [_Conn(category=Category.WEB_SEARCH, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"
    assert health.unresolved_needs == []


def test_morning_briefing_active_with_financial_and_news():
    from openlia.departments import MorningBriefingDepartment

    dept = MorningBriefingDepartment()
    connectors = [
        _Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED),
        _Conn(category=Category.NEWS, status=ConnectorStatus.VALIDATED),
    ]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"


def test_morning_briefing_active_with_financial_and_web_search_only():
    from openlia.departments import MorningBriefingDepartment

    dept = MorningBriefingDepartment()
    connectors = [
        _Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED),
        _Conn(category=Category.WEB_SEARCH, status=ConnectorStatus.VALIDATED),
    ]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "active"


def test_morning_briefing_disabled_without_news_or_web_search():
    from openlia.departments import MorningBriefingDepartment

    dept = MorningBriefingDepartment()
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "disabled"
    assert "news" in health.reason and "web_search" in health.reason


def test_macro_research_disabled_without_web_search_connector():
    dept = MacroResearchDepartment()
    # FINANCIAL alone is no longer enough — WEB_SEARCH is the one required category.
    connectors = [_Conn(category=Category.FINANCIAL, status=ConnectorStatus.VALIDATED)]
    health = check_dept_health(dept, validated_connectors=connectors, runner_specs=[])
    assert health.status == "disabled"
    assert Category.WEB_SEARCH in health.missing_categories
