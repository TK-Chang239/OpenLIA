from openlia.connectors.types import Category
from openlia.departments.morning_briefing import MorningBriefingDepartment


def test_mb_identifies_itself():
    d = MorningBriefingDepartment()
    assert d.name == "morning_briefing"
    assert d.display_name == "Morning Briefings"
    assert d.prompt_name == "morning_briefing"


def test_mb_single_mode():
    assert set(MorningBriefingDepartment().valid_modes) == {"morning_briefing"}


def test_mb_required_categories():
    # Spec §10.1: MB needs both financial and news.
    assert set(MorningBriefingDepartment.required_categories) == {
        Category.FINANCIAL,
        Category.NEWS,
    }


def test_mb_optional_categories():
    assert Category.WEB_SEARCH in MorningBriefingDepartment.optional_categories


def test_mb_does_not_require_runner():
    assert MorningBriefingDepartment.requires_runner is False
    assert MorningBriefingDepartment.disable_runtime_routing is False


def test_mb_has_no_extra_tools():
    assert MorningBriefingDepartment().extra_tools == ()


def test_mb_tier_is_everyday():
    assert MorningBriefingDepartment().tier == "everyday"
