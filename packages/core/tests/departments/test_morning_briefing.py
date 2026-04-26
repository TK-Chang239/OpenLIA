from openlia.departments.morning_briefing import MorningBriefingDepartment


def test_mb_identifies_itself():
    d = MorningBriefingDepartment()
    assert d.name == "morning_briefing"
    assert d.display_name == "Morning Briefings"
    assert d.prompt_name == "morning_briefing"


def test_mb_single_mode():
    assert set(MorningBriefingDepartment().valid_modes) == {"morning_briefing"}


def test_mb_basic_data_requirements():
    reqs = MorningBriefingDepartment().data_requirement_types
    for name in ("company_news", "economic_events"):
        assert name in reqs


def test_mb_optional_data_requirements():
    soft = MorningBriefingDepartment().optional_requirement_types
    for name in (
        "stock_quote",
        "historical_prices",
        "macro_indicator",
    ):
        assert name in soft


def test_mb_has_no_extra_tools():
    assert MorningBriefingDepartment().extra_tools == ()


def test_mb_tier_is_everyday():
    assert MorningBriefingDepartment().tier == "everyday"
