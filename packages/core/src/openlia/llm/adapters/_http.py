from __future__ import annotations

import re

import httpx

from openlia.llm.exceptions import (
    AuthError,
    CapabilityError,
    ContextLengthError,
    ModelNotFoundError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
)

_CONTEXT_LENGTH_RE = re.compile(r"(?:context|maximum).*?(\d{3,7})\s*tokens?", re.IGNORECASE)


def make_client(
    *,
    base_url: str,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        headers=headers or {},
    )


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def status_to_exception(
    *,
    status_code: int,
    body_text: str,
    headers: dict[str, str] | None = None,
) -> None:
    headers = {k.lower(): v for k, v in (headers or {}).items()}

    if status_code in (401, 403):
        raise AuthError(f"authentication failed ({status_code}): {body_text[:200]}")

    if status_code == 429:
        retry_after = _parse_retry_after(headers.get("retry-after"))
        raise RateLimitError(
            f"rate limited: {body_text[:200]}",
            retry_after_seconds=retry_after,
        )

    if status_code == 404:
        raise ModelNotFoundError(f"not found: {body_text[:200]}")

    if 500 <= status_code < 600:
        raise ProviderOutageError(f"upstream {status_code}: {body_text[:200]}")

    if status_code == 400:
        match = _CONTEXT_LENGTH_RE.search(body_text)
        if match:
            raise ContextLengthError(body_text[:300], limit=int(match.group(1)))
        raise CapabilityError(f"bad request: {body_text[:200]}")

    raise TransportError(f"unexpected status {status_code}: {body_text[:200]}")


def wrap_httpx_error(exc: httpx.HTTPError) -> TransportError:
    return TransportError(f"{type(exc).__name__}: {exc!s}")
