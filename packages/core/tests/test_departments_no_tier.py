import pytest
from openlia.departments import (
    EarningsUpdateDepartment,
    EquityResearchDepartment,
    MacroResearchDepartment,
    MorningBriefingDepartment,
    PanicThermometerDepartment,
    RetailSentimentDepartment,
    SecretaryDepartment,
)


@pytest.mark.parametrize(
    "cls",
    [
        SecretaryDepartment,
        EquityResearchDepartment,
        EarningsUpdateDepartment,
        MorningBriefingDepartment,
        PanicThermometerDepartment,
        MacroResearchDepartment,
        RetailSentimentDepartment,
    ],
)
def test_department_has_no_tier_attr(cls):
    assert not hasattr(cls, "tier"), f"{cls.__name__} still declares a tier"
    assert not hasattr(cls(), "tier")


def test_get_enabled_default_tiers_removed():
    import openlia.departments as dpt

    assert not hasattr(dpt, "get_enabled_default_tiers")
