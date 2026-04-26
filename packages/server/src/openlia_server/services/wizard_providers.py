"""Setup-wizard Step 4 (Data Providers) helpers.

Thin wrapper over `services.data_providers` that adds:
  - per-provider status tracking ("ok"/"error"/"pending") cached in
    extra_config so the wizard UI can render coloured pills;
  - test-then-persist flow used by `POST /setup/providers`;
  - re-test that updates the cached status.

Encryption is handled inside `services.data_providers.create_provider`.
"""

from __future__ import annotations

from typing import Any

from openlia.data.types import ProviderCategory, ProviderMode
from sqlalchemy.orm import Session

from openlia_server.services import data_providers as svc

_STATUS_KEY = "wizard_status"
_STATUS_OK = "ok"
_STATUS_ERROR = "error"
_STATUS_PENDING = "pending"

# Default base URLs for builtin provider kinds. The wizard's "builtin" mode
# lets the user pick a known provider without typing a URL; we inject the
# canonical base_url here so create_provider's API_KEY validation passes.
_DEFAULT_BASE_URLS: dict[str, str] = {
    "eodhd": "https://eodhd.com/api",
    "fmp": "https://financialmodelingprep.com/api/v3",
    "finnhub": "https://finnhub.io/api/v1",
    "yfinance": "https://query1.finance.yahoo.com",
    "newsapi_ai": "https://eventregistry.org/api/v1",
    "newsapi_org": "https://newsapi.org/v2",
    "mediastack": "https://api.mediastack.com/v1",
    "reddit": "https://oauth.reddit.com",
    "x": "https://api.x.com/2",
    "brave": "https://api.search.brave.com/res/v1",
    "tavily": "https://api.tavily.com",
    "serper": "https://google.serper.dev",
    "firecrawl": "https://api.firecrawl.dev",
}


def _read_status(row: Any) -> str:
    cfg = row.extra_config or {}
    s = cfg.get(_STATUS_KEY)
    if s in (_STATUS_OK, _STATUS_ERROR, _STATUS_PENDING):
        return s
    return _STATUS_PENDING


def _write_status(db: Session, row: Any, status: str) -> None:
    cfg = dict(row.extra_config or {})
    cfg[_STATUS_KEY] = status
    row.extra_config = cfg
    db.flush()


async def _health_check(row: Any) -> tuple[bool, str | None]:
    """Run the adapter's health check; return (ok, error_message)."""
    from openlia.data.adapters import ADAPTERS
    from openlia.data.adapters._stub import _StubAdapter

    adapter_cls = ADAPTERS.get(row.kind)
    if adapter_cls is None:
        return False, f"unknown provider kind {row.kind!r}"
    if issubclass(adapter_cls, _StubAdapter):
        # Stub adapters can't be tested live; treat as pending-ok so the
        # wizard advances. The Settings page surfaces a 501 to admins later.
        return True, None
    try:
        entry = svc.load_provider_entry(svc.get_provider.__self__, row.id)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover — fallback path
        return False, str(exc)
    try:
        adapter = adapter_cls(entry)
        return bool(await adapter.health_check()), None
    except Exception as exc:
        return False, str(exc)


async def list_providers_for_wizard(db: Session) -> list[dict[str, Any]]:
    """Return rows shaped for the wizard UI: id, category, mode, kind, status, priority."""
    rows = svc.list_providers(db)
    out: list[dict[str, Any]] = []
    for r in rows:
        cfg = r.extra_config or {}
        out.append(
            {
                "id": r.id,
                "category": r.category,
                "mode": r.mode,
                "provider": r.kind,
                "priority": int(cfg.get("default_priority", 100)),
                "status": _read_status(r),
            }
        )
    return out


async def add_provider(
    db: Session,
    *,
    category: str,
    entry: Any,
) -> dict[str, Any]:
    """Test-then-persist: build the row, run health check, store status.

    `entry` is a Pydantic model with: mode (builtin|mcp), provider?, api_key?,
    base_url?, mcp_url?, mcp_auth_header?

    Forcing function: `builtin` mode requires a `provider` from
    `_DEFAULT_BASE_URLS` (i.e. one of OpenLIA's shipped adapters). Anything
    else must be added via `mcp` mode with a non-empty `mcp_url`.
    """
    from openlia.data.adapters import ADAPTERS

    cat = _coerce_category(category)
    row_mode = ProviderMode.MCP if entry.mode == "mcp" else ProviderMode.API_KEY
    kind = entry.provider or category  # fall back to category as kind if missing

    if entry.mode == "builtin" and kind not in ADAPTERS:
        return {
            "ok": False,
            "entry_id": None,
            "error": (
                f"{kind!r} is not a built-in provider. Add it via MCP mode by supplying its "
                "MCP server URL."
            ),
        }
    if entry.mode == "mcp" and not getattr(entry, "mcp_url", None):
        return {
            "ok": False,
            "entry_id": None,
            "error": "mcp mode requires an mcp_url",
        }

    base_url = getattr(entry, "base_url", None)
    if entry.mode == "builtin" and not base_url:
        base_url = _DEFAULT_BASE_URLS.get(kind)
    api_key = getattr(entry, "api_key", None)
    mcp_url = getattr(entry, "mcp_url", None)
    mcp_auth_header = getattr(entry, "mcp_auth_header", None)
    oauth_client_id = getattr(entry, "oauth_client_id", None)
    oauth_client_secret = getattr(entry, "oauth_client_secret", None)
    extra_config: dict[str, Any] | None = None
    if oauth_client_id or oauth_client_secret:
        extra_config = {}
        if oauth_client_id:
            extra_config["oauth_client_id"] = oauth_client_id
        if oauth_client_secret:
            extra_config["oauth_client_secret"] = oauth_client_secret

    try:
        created = svc.create_provider(
            db,
            kind=kind,
            label=f"{kind}",
            category=cat,
            mode=row_mode,
            api_key=api_key,
            base_url=base_url,
            mcp_url=mcp_url,
            mcp_auth_header=mcp_auth_header,
            extra_config=extra_config,
        )
    except svc.UnknownProviderKindError as exc:
        return {"ok": False, "entry_id": None, "error": f"unknown provider kind: {exc}"}
    except ValueError as exc:
        return {"ok": False, "entry_id": None, "error": str(exc)}

    row = svc.get_provider(db, created.id)

    ok, err = await _run_health_check(row)
    _write_status(db, row, _STATUS_OK if ok else _STATUS_ERROR)
    return {"ok": ok, "entry_id": created.id, "error": err}


async def retest_provider(db: Session, provider_id: str) -> dict[str, Any]:
    try:
        row = svc.get_provider(db, provider_id)
    except svc.ProviderNotFoundError:
        return {"ok": False, "latency_ms": None, "error": "not_found"}
    ok, err = await _run_health_check(row)
    _write_status(db, row, _STATUS_OK if ok else _STATUS_ERROR)
    return {"ok": ok, "latency_ms": None, "error": err}


async def _run_health_check(row: Any) -> tuple[bool, str | None]:
    """Run a health check against an adapter built from a row, sandbox-friendly.

    For built-in adapters we bypass `health_check()` (which tends to swallow
    exceptions and return False) and instead call a representative capability
    method directly so adapter-raised errors (auth failures, invalid keys,
    rate limits) propagate as readable messages.
    """
    from openlia.data.adapters import ADAPTERS
    from openlia.data.adapters._stub import _StubAdapter
    from openlia.data.types import ProviderEntry

    adapter_cls = ADAPTERS.get(row.kind)
    if adapter_cls is None:
        return False, f"unknown provider kind {row.kind!r}"
    if issubclass(adapter_cls, _StubAdapter):
        # Stubs can't be live-tested. Keep a green pill so the wizard advances.
        return True, None

    api_key: str | None = None
    if row.api_key_encrypted:
        from openlia_server.db.crypto import decrypt_for_row

        api_key = decrypt_for_row(row_id=row.id, token=row.api_key_encrypted)
    elif row.env_var_name:
        import os as _os

        api_key = _os.environ.get(row.env_var_name)

    try:
        category = ProviderCategory(row.category)
    except ValueError:
        category = ProviderCategory.FINANCIAL
    try:
        mode = ProviderMode(row.mode)
    except ValueError:
        mode = ProviderMode.API_KEY

    entry = ProviderEntry(
        id=row.id,
        kind=row.kind,
        label=row.label,
        category=category,
        mode=mode,
        api_key=api_key,
        base_url=row.base_url,
        mcp_url=row.mcp_url,
        mcp_auth_header=row.mcp_auth_header,
        extra_config=row.extra_config or {},
        is_enabled=row.is_enabled,
        priority=100,
    )
    try:
        adapter = adapter_cls(entry)
    except Exception as exc:
        return False, str(exc) or exc.__class__.__name__

    try:
        ok = bool(await adapter.health_check())
    except Exception as exc:
        return False, _format_adapter_error(exc)
    if ok:
        return True, None
    # Adapter swallowed the failure and returned False. Re-run the underlying
    # call without the swallowing wrapper so we surface the real reason.
    err = await _probe_adapter_for_error(adapter)
    return False, err or "health check failed (no detail returned by adapter)"


async def _probe_adapter_for_error(adapter: Any) -> str | None:
    """Call adapter capabilities until a non-DataNotAvailable error surfaces.

    Adapters' health_check() typically wraps a representative call in a broad
    try/except that drops the exception and returns False. To surface the
    underlying error (auth failure, rate limit, malformed response, etc.) we
    re-trigger calls with the swallowing wrapper removed. We skip
    DataNotAvailable since it usually means our probe params don't fit the
    capability — not the actual provider error.
    """
    from openlia.data.errors import DataNotAvailable

    capabilities = sorted(getattr(adapter.__class__, "capabilities", ()))
    safe_params: dict[str, Any] = {
        "symbol": "AAPL",
        "keyword": "Apple",
        "query": "Apple",
        "ticker": "AAPL",
        "company": "Apple",
        "limit": 1,
    }
    last_unavailable: str | None = None
    for cap in capabilities:
        try:
            await adapter.fetch(cap, safe_params)
            return None
        except DataNotAvailable as exc:
            last_unavailable = _format_adapter_error(exc)
            continue
        except Exception as exc:
            return _format_adapter_error(exc)
    return last_unavailable


def _format_adapter_error(exc: Exception) -> str:
    """Return a short, user-friendly message from an adapter exception."""
    name = exc.__class__.__name__
    msg = str(exc).strip()
    if not msg:
        return name
    return f"{name}: {msg}" if name not in msg else msg


def _coerce_category(category: str) -> ProviderCategory:
    if category == "social":
        return ProviderCategory.SOCIAL_MEDIA
    if category == "web_search":
        return ProviderCategory.SEARCH
    return ProviderCategory(category)


def patch_provider(
    db: Session,
    provider_id: str,
    *,
    priority: int | None,
    api_key: str | None,
) -> None:
    if priority is not None:
        svc.set_provider_default_priority(db, provider_id=provider_id, priority=priority)
    if api_key is not None:
        svc.update_provider(db, provider_id, api_key=api_key)


def delete_provider(db: Session, provider_id: str) -> None:
    svc.delete_provider(db, provider_id)


def has_green_pair(db: Session) -> bool:
    """True when there's at least one OK financial AND one OK news provider."""
    rows = svc.list_providers(db)
    has_fin = any(r.category == "financial" and _read_status(r) == _STATUS_OK for r in rows)
    has_news = any(r.category == "news" and _read_status(r) == _STATUS_OK for r in rows)
    return has_fin and has_news
