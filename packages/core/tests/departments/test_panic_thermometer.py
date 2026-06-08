from openlia.connectors.types import Category
from openlia.departments.panic_thermometer import PanicThermometerDepartment


def test_pt_identifies_itself():
    d = PanicThermometerDepartment()
    assert d.name == "panic_thermometer"
    assert d.display_name == "Panic Thermometer"
    assert d.is_dashboard is True


def test_pt_has_five_panels():
    d = PanicThermometerDepartment()
    assert set(d.panel_ids) == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }


def test_pt_required_categories():
    # Spec §10.1.
    assert PanicThermometerDepartment.required_categories == (Category.FINANCIAL,)


def test_pt_optional_categories():
    assert Category.NEWS in PanicThermometerDepartment.optional_categories


def test_pt_disable_runtime_routing():
    assert PanicThermometerDepartment.disable_runtime_routing is False


def test_pt_has_no_report_modes():
    d = PanicThermometerDepartment()
    assert d.valid_modes == ()


def test_pt_has_no_extra_tools():
    assert PanicThermometerDepartment().extra_tools == ()
