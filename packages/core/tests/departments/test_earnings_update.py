from openlia.connectors.types import Category
from openlia.departments.earnings_update import EarningsUpdateDepartment


def test_eu_identifies_itself():
    d = EarningsUpdateDepartment()
    assert d.name == "earnings_update"
    assert d.display_name == "Earnings Updates"
    assert d.prompt_name == "earnings_update"


def test_eu_single_mode():
    assert set(EarningsUpdateDepartment().valid_modes) == {"earnings_analysis"}


def test_eu_required_categories():
    # Spec §10.1.
    assert EarningsUpdateDepartment.required_categories == (Category.FINANCIAL,)


def test_eu_optional_categories():
    assert Category.NEWS in EarningsUpdateDepartment.optional_categories


def test_eu_disable_runtime_routing():
    assert EarningsUpdateDepartment.disable_runtime_routing is False


def test_eu_has_no_extra_tools():
    assert EarningsUpdateDepartment().extra_tools == ()
