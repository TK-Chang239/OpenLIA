from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
)


def test_data_not_available_has_provider_and_capability() -> None:
    err = DataNotAvailable(
        provider_kind="eodhd",
        capability="stock_quote",
        reason="symbol not found",
    )
    assert err.provider_kind == "eodhd"
    assert err.capability == "stock_quote"
    assert err.reason == "symbol not found"
    assert "eodhd" in str(err)
    assert "stock_quote" in str(err)
    assert "symbol not found" in str(err)


def test_rate_limit_error_carries_retry_after_seconds() -> None:
    err = RateLimitError(
        provider_kind="eodhd",
        retry_after_seconds=30,
    )
    assert err.retry_after_seconds == 30
    assert err.provider_kind == "eodhd"


def test_rate_limit_retry_after_defaults_to_none() -> None:
    err = RateLimitError(provider_kind="fmp")
    assert err.retry_after_seconds is None


def test_data_source_error_wraps_status_and_detail() -> None:
    err = DataSourceError(
        provider_kind="eodhd",
        status_code=500,
        detail="internal server error",
    )
    assert err.status_code == 500
    assert err.detail == "internal server error"


def test_all_errors_subclass_data_provider_error() -> None:
    assert issubclass(DataNotAvailable, DataProviderError)
    assert issubclass(RateLimitError, DataProviderError)
    assert issubclass(DataSourceError, DataProviderError)
