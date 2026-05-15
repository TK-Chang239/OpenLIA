from __future__ import annotations

import re
import ssl

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

# Errors that escape httpx as raw OSError-family / SSL faults. These come up
# under sustained load (multi-turn agentic loops) when a pooled keepalive
# connection's TLS state goes bad mid-flight. Treating them as transient lets
# `with_retries` retry on a fresh connection.
TRANSIENT_NETWORK_ERRORS: tuple[type[BaseException], ...] = (
    httpx.HTTPError,
    ssl.SSLError,
    ConnectionError,
    TimeoutError,
    OSError,  # last-resort umbrella; httpx wraps most of these already
)

_CONTEXT_LENGTH_RE = re.compile(r"(?:context|maximum).*?(\d{3,7})\s*tokens?", re.IGNORECASE)


def make_client(
    *,
    base_url: str,
    timeout: httpx.Timeout | float | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    # httpx-level transport retries handle low-level TLS / connect resets that
    # fire before any HTTP response arrives. with_retries handles the
    # application-level retries on top.
    #
    # Default timeout is generous on read because long-context models
    # (gpt-5.4, claude-opus-4-7) routinely take minutes to emit the first
    # byte on large reasoning + tool-loop turns. Connect/write/pool stay
    # short so legitimately broken sockets surface fast.
    if timeout is None:
        timeout = httpx.Timeout(connect=15.0, read=600.0, write=60.0, pool=15.0)
    transport = httpx.AsyncHTTPTransport(retries=2)
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        headers=headers or {},
        transport=transport,
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


def wrap_httpx_error(exc: BaseException) -> TransportError:
    return TransportError(f"{type(exc).__name__}: {exc!s}")
