from openlia_server.services.subject_normalize import normalize_subject


def test_normalize_lowercases_and_trims() -> None:
    assert normalize_subject("MSFT") == "msft"
    assert normalize_subject(" msft ") == "msft"
    assert normalize_subject(" MSFT\n") == "msft"


def test_normalize_none_or_empty_returns_empty_string() -> None:
    assert normalize_subject(None) == ""
    assert normalize_subject("") == ""
    assert normalize_subject("   ") == ""


def test_normalize_preserves_internal_punctuation() -> None:
    # Exchange suffix not smoothed in v1 — different exchanges count as different.
    assert normalize_subject("MSFT.US") == "msft.us"
    assert normalize_subject("MSFT.US") != normalize_subject("MSFT.NASDAQ")
