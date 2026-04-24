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


def test_pt_basic_data_requirements():
    reqs = PanicThermometerDepartment().data_requirement_types
    for name in ("historical_prices", "stock_quote", "economic_events"):
        assert name in reqs


def test_pt_optional_data_requirements():
    soft = PanicThermometerDepartment().optional_requirement_types
    assert "company_news" in soft


def test_pt_has_no_report_modes():
    d = PanicThermometerDepartment()
    assert d.valid_modes == ()


def test_pt_has_no_extra_tools():
    assert PanicThermometerDepartment().extra_tools == ()
