from openlia.panic_thermometer.presets import PT_PRESETS


def test_presets_cover_all_panels():
    assert set(PT_PRESETS.keys()) == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }


def test_each_panel_has_three_presets():
    for panel, presets in PT_PRESETS.items():
        assert len(presets) == 3, f"{panel} should ship 3 presets, got {list(presets)}"


def test_report_defaults_match_panel_default():
    from openlia.panic_thermometer.panels import PANELS

    for panel_id, panel in PANELS.items():
        report_defaults = PT_PRESETS[panel_id]["report_defaults"]
        assert report_defaults["rules"] == panel.default_ruleset["rules"]


def test_oil_ma_relative_uses_ma200():
    rs = PT_PRESETS["oil"]["ma_relative"]
    formulas = " ".join(r["formula"] for r in rs["rules"])
    assert "ma200" in formulas or "price_vs_ma200" in formulas


def test_oil_volatility_adjusted_uses_atr():
    rs = PT_PRESETS["oil"]["volatility_adjusted"]
    formulas = " ".join(r["formula"] for r in rs["rules"])
    assert "atr_14" in formulas


def test_every_preset_is_parseable_by_formula_engine():
    from openlia.formula import FormulaError, parse

    for panel_id, presets in PT_PRESETS.items():
        for preset_name, rs in presets.items():
            for rule in rs["rules"]:
                try:
                    parse(rule["formula"])
                except FormulaError as exc:  # pragma: no cover - informational
                    raise AssertionError(
                        f"{panel_id}/{preset_name} rule '{rule['formula']}' failed to parse: {exc}"
                    ) from exc
