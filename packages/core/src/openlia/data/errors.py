"""Typed errors for data provider operations.

Per data-provider-design.md, three categories:
- DataNotAvailable: the provider does not cover this data (normal outcome; the
  LLM must say "data unavailable", never hallucinate).
- RateLimitError: provider returned 429 or an equivalent rate-limit signal.
- DataSourceError: unexpected 5xx / network / parse failure.

All three subclass DataProviderError for blanket try/except at the call site.
"""


class DataProviderError(Exception):
    """Base class for all data provider errors."""


class DataNotAvailable(DataProviderError):
    """The configured provider cannot satisfy this capability for these params.

    Not an exceptional runtime condition — the caller is expected to convert
    this into a normal tool-result payload telling the LLM the data is missing.
    """

    def __init__(
        self,
        *,
        provider_kind: str,
        capability: str,
        reason: str,
    ) -> None:
        self.provider_kind = provider_kind
        self.capability = capability
        self.reason = reason
        super().__init__(f"{provider_kind}:{capability} unavailable: {reason}")


class RateLimitError(DataProviderError):
    """Provider rate limit hit.

    `retry_after_seconds` is populated when the provider's response indicates
    a backoff window; otherwise None (caller decides the backoff strategy).
    """

    def __init__(
        self,
        *,
        provider_kind: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.provider_kind = provider_kind
        self.retry_after_seconds = retry_after_seconds
        msg = f"{provider_kind} rate limited"
        if retry_after_seconds is not None:
            msg += f" (retry after {retry_after_seconds}s)"
        super().__init__(msg)


class DataSourceError(DataProviderError):
    """Unexpected provider error — 5xx, timeout, malformed response."""

    def __init__(
        self,
        *,
        provider_kind: str,
        status_code: int | None = None,
        detail: str = "",
    ) -> None:
        self.provider_kind = provider_kind
        self.status_code = status_code
        self.detail = detail
        parts = [f"{provider_kind} source error"]
        if status_code is not None:
            parts.append(f"status={status_code}")
        if detail:
            parts.append(detail)
        super().__init__("; ".join(parts))
