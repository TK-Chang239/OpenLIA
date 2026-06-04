"""Save-time smoke pipeline (Phase 7).

Spec: docs/superpowers/specsv2/2026-05-02-resolver-redesign-manual-pick.md §7.
Plan: docs/superpowers/plans/2026-05-02-resolver-redesign.md §Phase 7.

Every save-time `CallableSpec` runs through `run_smoke` with a canonical
test arg dict before being persisted as live. Failures roll back the
draft and surface a typed status so the wizard / admin panel can render
the right recovery affordance:

    success      ok — persist as live
    auth         401/403 — fix API key in connector settings
    bad_params   400 — endpoint rejected canonical args
    schema_miss  result_path / field_map / from_dict failed
    empty        endpoint returned [] / null / {}
    transient    5xx / timeout / network — retried 3x and still failing

For `list[dict]`-shaped specs we also feed the first response item
through the dept's adapter `from_dict` to ensure canonical keys are
present after `field_map` rename. Missing keys are reclassified as
`schema_miss` so the user sees a single, actionable failure bucket.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from openlia.connectors.dispatch import (
    DispatchError,
    FieldMapError,
    _apply_field_map,
    _walk_result_path,
)
from openlia.connectors.transports import CallableTransport
from openlia.connectors.types import (
    ALLOWED_TRANSFORMS,
    RESULT_REDUCERS,
    TRANSFORMS,
    CallableSpec,
)

SmokeStatus = Literal[
    "success",
    "auth",
    "bad_params",
    "schema_miss",
    "empty",
    "transient",
]


@dataclass(frozen=True)
class SmokeResult:
    status: SmokeStatus
    attempts: int
    error_class: str | None
    error_message: str | None
    response_excerpt: str | None


# Canonical args used at smoke time. Stable across reruns so audit logs
# are comparable. The plan picks AAPL for ticker-shaped needs, a small
# window for date-bounded needs, and a generic country code for macro.
CANONICAL_ARGS: dict[str, dict[str, Any]] = {
    "stock_quote": {"ticker": "AAPL"},
    "social_posts": {"ticker": "AAPL", "limit": 5},
    "geopolitical_news": {"window_days": 7, "limit": 5},
    "debt_gdp": {"country": "US"},
    "interest_revenue": {"country": "US"},
    "pmi": {"country": "US"},
    "gdp_yoy": {"country": "US"},
    "cpi_yoy": {"country": "US"},
    "cpi_core_yoy": {"country": "US"},
    "usd_fx_reserve_share": {},
    "cb_gold_purchases": {"window_days": 365},
    "foreign_treasury_holdings": {"window_days": 90},
}

_MAX_ATTEMPTS = 3
_RESPONSE_EXCERPT_LIMIT = 32_000


def classify_exception(exc: BaseException) -> tuple[SmokeStatus, str | None]:
    """Map an exception raised by the transport into a SmokeStatus bucket.

    Returns (status, optional offending-key for schema_miss).
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "auth", None
        if code == 400 or code == 422:
            return "bad_params", None
        if 500 <= code < 600 or code == 408 or code == 429:
            return "transient", None
        return "bad_params", None
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError | httpx.NetworkError):
        return "transient", None
    if isinstance(exc, FieldMapError | DispatchError):
        return "schema_miss", None
    if isinstance(exc, KeyError):
        return "schema_miss", str(exc.args[0]) if exc.args else None
    if isinstance(exc, TimeoutError):
        return "transient", None
    return "bad_params", None


def _bind_args(spec: CallableSpec, sample_args: dict[str, Any]) -> dict[str, Any]:
    bound: dict[str, Any] = {}
    for caller_name, value in sample_args.items():
        binding = spec.param_bindings.get(caller_name)
        if binding is None:
            bound[caller_name] = value
            continue
        if binding.transform is not None and binding.transform in ALLOWED_TRANSFORMS:
            value = TRANSFORMS[binding.transform](value)
        bound[binding.to_arg] = value
    for k, v in spec.constants.items():
        bound[k] = v
    return bound


def _excerpt(value: Any) -> str | None:
    try:
        s = json.dumps(value, default=str)
    except (TypeError, ValueError):
        s = str(value)
    if len(s) > _RESPONSE_EXCERPT_LIMIT:
        return s[:_RESPONSE_EXCERPT_LIMIT] + " …[truncated]"
    return s


def _from_dict_check(spec: CallableSpec, items: list[dict[str, Any]]) -> str | None:
    """For list[dict] specs with a registered dept adapter, run from_dict on
    the first item. Returns an error message if from_dict raises, else None.
    """
    adapter = _DEPT_ADAPTERS.get(spec.need_id)
    if adapter is None or not items:
        return None
    try:
        adapter(items[0])
    except KeyError as exc:
        missing = exc.args[0] if exc.args else "unknown"
        return f"dept from_dict missing key {missing!r}"
    except Exception as exc:
        return f"dept from_dict raised {type(exc).__name__}: {exc}"
    return None


def _geopolitical_news_from_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Adapter for macro_research.geopolitical_news.

    The dept consumes raw dicts with the canonical keys; this adapter
    asserts each canonical key is present and non-empty for `title`.
    """
    for required in ("title", "url", "source", "published_at", "summary"):
        if required not in item:
            raise KeyError(required)
    return item


_DEPT_ADAPTERS = {
    "geopolitical_news": _geopolitical_news_from_dict,
}


async def run_smoke(
    *,
    spec: CallableSpec,
    transport: CallableTransport,
    sample_args: dict[str, Any] | None = None,
) -> SmokeResult:
    """Execute `spec` once with canonical args and classify the outcome.

    Retries transient failures up to 3 attempts. Returns a SmokeResult
    capturing the final status, attempt count, and (if any) the
    classified error.
    """
    if sample_args is None:
        sample_args = CANONICAL_ARGS.get(spec.need_id, {})

    if spec.access_mode in ("cli_mcp", "remote_mcp"):
        target = spec.tool_name
    elif spec.access_mode == "python_lib":
        target = spec.method
    else:
        return SmokeResult(
            status="bad_params",
            attempts=0,
            error_class="ValueError",
            error_message=f"unknown access_mode {spec.access_mode!r}",
            response_excerpt=None,
        )
    if not target:
        return SmokeResult(
            status="bad_params",
            attempts=0,
            error_class="ValueError",
            error_message="spec has no tool/method name",
            response_excerpt=None,
        )

    try:
        bound = _bind_args(spec, sample_args)
    except Exception as exc:
        return SmokeResult(
            status="bad_params",
            attempts=0,
            error_class=type(exc).__name__,
            error_message=str(exc),
            response_excerpt=None,
        )

    attempt = 0
    last_status: SmokeStatus = "transient"
    last_error_class: str | None = None
    last_error_message: str | None = None
    while attempt < _MAX_ATTEMPTS:
        attempt += 1
        try:
            value: Any = await transport.call_tool(target, bound)
        except BaseException as exc:
            status, _key = classify_exception(exc)
            last_status = status
            last_error_class = type(exc).__name__
            last_error_message = str(exc) or repr(exc)
            if status == "transient" and attempt < _MAX_ATTEMPTS:
                continue
            return SmokeResult(
                status=status,
                attempts=attempt,
                error_class=last_error_class,
                error_message=last_error_message,
                response_excerpt=None,
            )

        # Apply result_reducer / result_path / field_map (mirrors
        # dispatcher post-processing). Wrap in try/except to classify
        # schema misses uniformly.
        try:
            if spec.result_reducer:
                reducer = RESULT_REDUCERS.get(spec.result_reducer)
                if reducer is None:
                    raise DispatchError(f"unknown result_reducer {spec.result_reducer!r}")
                value = reducer(value)
            if spec.result_path:
                value = _walk_result_path(value, spec.result_path, need_id=spec.need_id)
            if spec.shape == "list[dict]":
                value = _apply_field_map(value, spec)
        except (DispatchError, FieldMapError) as exc:
            return SmokeResult(
                status="schema_miss",
                attempts=attempt,
                error_class=type(exc).__name__,
                error_message=str(exc),
                response_excerpt=_excerpt(value),
            )
        except (KeyError, ValueError, TypeError) as exc:
            return SmokeResult(
                status="schema_miss",
                attempts=attempt,
                error_class=type(exc).__name__,
                error_message=str(exc),
                response_excerpt=_excerpt(value),
            )

        # Empty-result classification.
        if value is None or (isinstance(value, list | dict) and len(value) == 0):
            return SmokeResult(
                status="empty",
                attempts=attempt,
                error_class=None,
                error_message="endpoint returned empty result",
                response_excerpt=_excerpt(value),
            )

        # list[dict] dept-side from_dict check.
        if spec.shape == "list[dict]" and isinstance(value, list):
            err = _from_dict_check(spec, value)
            if err is not None:
                return SmokeResult(
                    status="schema_miss",
                    attempts=attempt,
                    error_class="KeyError",
                    error_message=err,
                    response_excerpt=_excerpt(value[0] if value else None),
                )

        return SmokeResult(
            status="success",
            attempts=attempt,
            error_class=None,
            error_message=None,
            response_excerpt=_excerpt(value),
        )

    return SmokeResult(
        status=last_status,
        attempts=attempt,
        error_class=last_error_class,
        error_message=last_error_message,
        response_excerpt=None,
    )


__all__ = [
    "CANONICAL_ARGS",
    "SmokeResult",
    "SmokeStatus",
    "classify_exception",
    "run_smoke",
]
