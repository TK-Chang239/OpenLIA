"""Tests for the v2.3 env-based wiring helper.

These verify the assembly path without making any network calls — adapters
are constructed but not invoked.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.runner import ReportRunner
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.stages import ClarifyStage
from openlia_server.services.v2_3_wiring import (
    _trim_eodhd_fundamentals,
    build_v2_3_runner_factory_from_env,
)


def test_returns_none_when_env_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENLIA_V2_3_CLARIFY_MODEL", raising=False)
    assert build_v2_3_runner_factory_from_env() is None


def test_returns_none_when_only_api_key_present(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENLIA_V2_3_CLARIFY_MODEL", raising=False)
    assert build_v2_3_runner_factory_from_env() is None


def test_returns_none_when_only_model_present(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENLIA_V2_3_CLARIFY_MODEL", "gpt-5.4-mini")
    assert build_v2_3_runner_factory_from_env() is None


# ---------------------------------------------------------------------------
# _trim_eodhd_fundamentals — General-section prose strip
# ---------------------------------------------------------------------------


def _general_payload() -> dict:
    return {
        "General": {
            # Prose / contact fields the trimmer must drop:
            "Description": (
                "Acme Corp designs and manufactures widgets. It operates "
                "through three segments: Widgets, Gadgets, and Other..."
            ),
            "Officers": {
                "0": {"Name": "Jane Doe", "Title": "CEO", "YearBorn": "1970"},
                "1": {"Name": "John Roe", "Title": "CFO", "YearBorn": "1975"},
            },
            "Address": "123 Main St",
            "AddressData": {"Street": "123 Main St", "City": "Anytown"},
            "Phone": "+1 555-555-5555",
            "WebURL": "https://acme.example",
            "LogoURL": "https://acme.example/logo.png",
            "InternationalDomestic": "International",
            # Structured metadata the trimmer must keep:
            "Code": "ACME",
            "Name": "Acme Corp",
            "Sector": "Industrials",
            "Industry": "Specialty Industrial Machinery",
            "GicSector": "Industrials",
            "CountryName": "USA",
            "CurrencyCode": "USD",
            "FullTimeEmployees": 50000,
            "IPODate": "1985-04-12",
        }
    }


def test_trim_drops_general_prose_and_contact_fields() -> None:
    out = _trim_eodhd_fundamentals(_general_payload())
    general = out["General"]
    for dropped in (
        "Description",
        "Officers",
        "Address",
        "AddressData",
        "Phone",
        "WebURL",
        "LogoURL",
        "InternationalDomestic",
    ):
        assert dropped not in general, f"{dropped!r} should be stripped"


def test_trim_keeps_general_structured_metadata() -> None:
    """Structured metadata stays — these are the fields the model
    legitimately uses to anchor a report (sector / industry / country
    / IPO date / employees)."""
    out = _trim_eodhd_fundamentals(_general_payload())
    general = out["General"]
    for kept in (
        "Code",
        "Name",
        "Sector",
        "Industry",
        "GicSector",
        "CountryName",
        "CurrencyCode",
        "FullTimeEmployees",
        "IPODate",
    ):
        assert kept in general, f"{kept!r} should be kept"


def test_trim_passes_through_non_dict_payload() -> None:
    """Defensive: a non-dict payload (None, error string) returns
    unchanged rather than raising — keeps the call site simple."""
    assert _trim_eodhd_fundamentals(None) is None  # type: ignore[arg-type]
    assert _trim_eodhd_fundamentals("oops") == "oops"  # type: ignore[arg-type]


def test_trim_leaves_general_intact_when_no_prose_fields_present() -> None:
    """A General section that's pure metadata round-trips unchanged."""
    payload = {"General": {"Code": "X", "Sector": "Tech"}}
    out = _trim_eodhd_fundamentals(payload)
    assert out == payload


def test_builds_factory_with_clarify_stage_when_env_complete(monkeypatch) -> None:
    """With both env vars set, the helper must produce a factory whose
    ReportRunner has a real ClarifyStage at V23Slot.CLARIFY (not a NoOp)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENLIA_V2_3_CLARIFY_MODEL", "gpt-5.4-mini")

    factory = build_v2_3_runner_factory_from_env()
    assert factory is not None

    runner = factory()
    assert isinstance(runner, ReportRunner)

    # Reach into the runner's stage registry to confirm CLARIFY is real
    # and backed by the env-configured LLM client (not a Fake).
    clarify_stage = runner._stages[V23Slot.CLARIFY]
    assert isinstance(clarify_stage, ClarifyStage)
    assert type(clarify_stage._client).__name__ == "LLMClarifierClient"
