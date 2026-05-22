"""Tests for GICS-based sector routing (sector_router.py).

Covers:
- Known GICS codes route to correct template names
- Unknown code falls back to default_template
- None falls back to default_template
- Empty string falls back to default_template
- All codes in the YAML file produce a non-empty template name
- clear_routing_cache() resets the cache
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.sector_router import (
    _get_code_map,
    clear_routing_cache,
    route_to_sector_template,
)

# ---------------------------------------------------------------------------
# Core routing assertions from spec §3
# ---------------------------------------------------------------------------


def test_banks_code_401010_routes_to_banks() -> None:
    clear_routing_cache()
    result = route_to_sector_template("401010")
    assert result == "banks_v2_2"


def test_pharma_code_352020_routes_to_pharma() -> None:
    clear_routing_cache()
    result = route_to_sector_template("352020")
    assert result == "pharma_v2_2"


def test_pharma_code_352010_routes_to_pharma() -> None:
    clear_routing_cache()
    result = route_to_sector_template("352010")
    assert result == "pharma_v2_2"


def test_reit_code_601010_routes_to_reits() -> None:
    clear_routing_cache()
    result = route_to_sector_template("601010")
    assert result == "reits_v2_2"


def test_energy_code_102020_routes_to_energy_ep() -> None:
    clear_routing_cache()
    result = route_to_sector_template("102020")
    assert result == "energy_ep_v2_2"


def test_insurance_code_403010_routes_to_insurance() -> None:
    clear_routing_cache()
    result = route_to_sector_template("403010")
    assert result == "insurance_v2_2"


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


def test_unknown_code_falls_back_to_default() -> None:
    clear_routing_cache()
    result = route_to_sector_template("999999")
    assert result == "stock_initiation_v2"


def test_none_code_falls_back_to_default() -> None:
    clear_routing_cache()
    result = route_to_sector_template(None)
    assert result == "stock_initiation_v2"


def test_empty_string_falls_back_to_default() -> None:
    clear_routing_cache()
    result = route_to_sector_template("")
    assert result == "stock_initiation_v2"


def test_msft_like_tech_code_falls_back_to_default() -> None:
    """GICS tech sub-industry 451020 (IT Services) has no sector module → default."""
    clear_routing_cache()
    result = route_to_sector_template("451020")
    assert result == "stock_initiation_v2"


def test_semi_tech_code_falls_back_to_default() -> None:
    """GICS 452030 (Semiconductors) has no sector module → default."""
    clear_routing_cache()
    result = route_to_sector_template("452030")
    assert result == "stock_initiation_v2"


# ---------------------------------------------------------------------------
# Exhaustive YAML integrity check
# ---------------------------------------------------------------------------


def test_all_yaml_codes_produce_non_empty_template() -> None:
    """Every code in sector_routing.yaml must map to a non-empty template name."""
    clear_routing_cache()
    code_map = _get_code_map()
    assert len(code_map) > 0, "sector_routing.yaml produced an empty code map"
    for code, template in code_map.items():
        assert template, f"Code {code!r} maps to an empty template name"


def test_routing_yaml_contains_expected_sectors() -> None:
    """All five sector groups must appear in the code map."""
    clear_routing_cache()
    code_map = _get_code_map()
    templates = set(code_map.values())
    expected = {"banks_v2_2", "reits_v2_2", "pharma_v2_2", "energy_ep_v2_2", "insurance_v2_2"}
    missing = expected - templates
    assert not missing, f"Missing sector templates in routing YAML: {missing}"


def test_banks_diversified_402020_routes_to_banks() -> None:
    """Diversified Financial Services (402020) should map to banks template."""
    clear_routing_cache()
    result = route_to_sector_template("402020")
    assert result == "banks_v2_2"


def test_reit_operating_companies_602010_routes_to_reits() -> None:
    clear_routing_cache()
    result = route_to_sector_template("602010")
    assert result == "reits_v2_2"


def test_insurance_life_health_403020_routes_to_insurance() -> None:
    clear_routing_cache()
    result = route_to_sector_template("403020")
    assert result == "insurance_v2_2"


# ---------------------------------------------------------------------------
# Cache clear
# ---------------------------------------------------------------------------


def test_clear_routing_cache_does_not_raise() -> None:
    clear_routing_cache()
    # Should be callable repeatedly without error.
    clear_routing_cache()
    result = route_to_sector_template("401010")
    assert result == "banks_v2_2"
