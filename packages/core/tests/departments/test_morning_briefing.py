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
    # MB hard-requires financial only. Headlines default to native web search,
    # so news/web_search connectors are optional rather than required-any-of.
    assert set(MorningBriefingDepartment.required_categories) == {Category.FINANCIAL}


def test_mb_no_required_any_of():
    # Headline source is no longer a required-any-of group; native web search
    # covers it, with NEWS/WEB_SEARCH connectors as optional enrichment.
    assert MorningBriefingDepartment.required_any_of == ()


def test_mb_optional_categories_cover_news_and_web_search():
    assert set(MorningBriefingDepartment.optional_categories) == {
        Category.NEWS,
        Category.WEB_SEARCH,
    }


def test_mb_disable_runtime_routing():
    assert MorningBriefingDepartment.disable_runtime_routing is False


def test_mb_has_no_extra_tools():
    assert MorningBriefingDepartment().extra_tools == ()
