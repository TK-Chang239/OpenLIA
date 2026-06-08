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
    # MB hard-requires financial. Headline source (news vs. web_search)
    # is expressed via required_any_of so either provider satisfies it.
    assert set(MorningBriefingDepartment.required_categories) == {Category.FINANCIAL}


def test_mb_required_any_of_covers_news_or_web_search():
    groups = MorningBriefingDepartment.required_any_of
    assert len(groups) == 1
    assert set(groups[0]) == {Category.NEWS, Category.WEB_SEARCH}


def test_mb_optional_categories_empty():
    # WEB_SEARCH was promoted into the required_any_of group.
    assert MorningBriefingDepartment.optional_categories == ()


def test_mb_disable_runtime_routing():
    assert MorningBriefingDepartment.disable_runtime_routing is False


def test_mb_has_no_extra_tools():
    assert MorningBriefingDepartment().extra_tools == ()
