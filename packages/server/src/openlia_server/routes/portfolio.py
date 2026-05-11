"""Portfolio routes — CRUD + analytics + CSV + price refresh + groups + search."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import portfolio as svc
from openlia_server.services import portfolio_prefs as prefs_svc
from openlia_server.services import portfolio_quotes as quotes_svc
from openlia_server.services.market_hours import Market
from openlia_server.services.portfolio_prices import (
    PortfolioPriceProvider,
    PriceCache,
    get_default_cache,
    get_default_provider,
)

_MARKET_DISPLAY_CURRENCY: dict[Market, str] = {"us": "USD", "twse": "TWD"}


def _resolve_market(raw: str | None) -> Market | None:
    """Translate the public query value ('us' | 'tw') into internal Market.

    Returns None for unset (no filter applied). Raises HTTPException(400)
    for unknown values so we fail loudly on typos.
    """
    if raw is None:
        return None
    v = raw.strip().lower()
    if v == "us":
        return "us"
    if v == "tw":
        return "twse"
    raise HTTPException(status_code=400, detail=f"unknown market {raw!r}")


logger = logging.getLogger(__name__)


class HoldingIn(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})
    ticker: str
    shares: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = "USD"
    notes: str | None = None
    groups: list[str] | None = None
    added_at_date: str | None = None


class HoldingPatch(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})
    shares: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = None
    notes: str | None = None
    groups: list[str] | None = None


class HoldingOut(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})
    id: str
    ticker: str
    name: str | None
    shares: Decimal | None
    cost_basis: Decimal | None
    currency: str
    groups: list[str]
    notes_text: str | None
    added_at: str
    updated_at: str


class SearchResultOut(BaseModel):
    ticker: str
    name: str | None
    exchange: str | None = None
    already_added: bool = False


class GroupCreateIn(BaseModel):
    name: str


class PrefsOut(BaseModel):
    refresh_cadence: str
    display_currency: str = "USD"


class PrefsPatchIn(BaseModel):
    refresh_cadence: str | None = None
    display_currency: str | None = None


class GroupRenameIn(BaseModel):
    new_name: str


class GroupReorderIn(BaseModel):
    order: list[str]


def _dto_to_out(dto: svc.HoldingDTO) -> HoldingOut:
    return HoldingOut(
        id=dto.id,
        ticker=dto.ticker,
        name=dto.name,
        shares=dto.shares,
        cost_basis=dto.cost_basis,
        currency=dto.currency,
        groups=list(dto.groups),
        notes_text=dto.notes_text,
        added_at=dto.added_at,
        updated_at=dto.updated_at,
    )


def _resolve_financial_adapter(request: Request) -> Any | None:
    return getattr(request.app.state, "financial_adapter", None)


def _run_backfill(
    db_session_factory: Callable[[], DBSession],
    ticker: str,
    adapter: Any | None,
) -> None:
    """Fire-and-forget helper for FastAPI BackgroundTasks.

    Runs the 5Y daily-history backfill against the configured financial
    adapter. Any failure is logged and swallowed — the holding row is
    already created at this point and the user shouldn't see backfill
    errors as request failures.
    """
    if adapter is None:
        return
    try:
        from openlia_server.services.portfolio_backfill import (
            AdapterDailyHistoryProvider,
            backfill_daily_history,
        )

        provider = AdapterDailyHistoryProvider(adapter)
        with db_session_factory() as session:
            backfill_daily_history(session, ticker=ticker, provider=provider, years=5)
    except Exception as exc:
        logger.warning("portfolio backfill background task failed for %s: %s", ticker, exc)


def _profile_to_search_row(symbol: str, payload: Any) -> SearchResultOut | None:
    """Map an EODHD `company_profile` General block to a search row.

    EODHD returns ``{"General": {"Code": "AAPL", "Name": "Apple Inc.",
    "Exchange": "NASDAQ", ...}}``. We tolerate raw dict shapes too.
    """
    if payload is None:
        return None
    if isinstance(payload, dict) and "General" in payload:
        general = payload.get("General") or {}
    else:
        general = payload if isinstance(payload, dict) else {}
    code = str(general.get("Code") or symbol).upper()
    name = general.get("Name")
    exchange = general.get("Exchange")
    return SearchResultOut(
        ticker=code,
        name=str(name) if name else None,
        exchange=str(exchange) if exchange else None,
    )


def build_portfolio_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
    price_cache: PriceCache | None = None,
    price_provider_factory: Callable[[], PortfolioPriceProvider] | None = None,
) -> APIRouter:
    require_user = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    cache = price_cache or get_default_cache()
    provider_factory = price_provider_factory or get_default_provider

    router = APIRouter(prefix="/portfolio", tags=["portfolio"])

    def _session() -> DBSession:
        return db_session_factory()

    @router.get("/holdings", response_model=list[HoldingOut])
    def list_holdings(market: str | None = None, user: User = require_user) -> list[HoldingOut]:
        market_filter = _resolve_market(market)
        with _session() as s:
            return [
                _dto_to_out(d) for d in svc.list_holdings(s, user_id=user.id, market=market_filter)
            ]

    @router.post("/holdings", response_model=HoldingOut, status_code=201)
    def create_holding(
        body: HoldingIn,
        background: BackgroundTasks,
        request: Request,
        market: str | None = None,
        user: User = require_user,
    ) -> HoldingOut:
        from datetime import UTC, datetime
        from datetime import date as date_cls
        from zoneinfo import ZoneInfo

        from openlia_server.services.market_hours import classify_market

        if body.shares is None:
            raise HTTPException(status_code=400, detail="shares is required")

        market_hint = _resolve_market(market)
        if market_hint is not None and classify_market(body.ticker) != market_hint:
            raise HTTPException(
                status_code=400,
                detail=(f"ticker {body.ticker!r} does not belong to market {market!r}"),
            )

        added_at_utc: datetime | None = None
        if body.added_at_date is not None:
            try:
                d = date_cls.fromisoformat(body.added_at_date)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(f"added_at_date must be YYYY-MM-DD, got {body.added_at_date!r}"),
                ) from exc
            if d > datetime.now(UTC).date():
                raise HTTPException(status_code=400, detail="added_at_date cannot be in the future")
            ticker_market = classify_market(body.ticker)
            if ticker_market == "twse":
                tz = ZoneInfo("Asia/Taipei")
            elif ticker_market == "us":
                tz = ZoneInfo("America/New_York")
            else:
                tz = UTC
            added_at_utc = datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz).astimezone(UTC)

        with _session() as s:
            try:
                dto = svc.create_holding(
                    s,
                    user_id=user.id,
                    ticker=body.ticker,
                    shares=body.shares,
                    cost_basis=body.cost_basis,
                    currency=body.currency,
                    notes=body.notes,
                    groups=body.groups,
                    added_at=added_at_utc,
                )
            except svc.DuplicateTickerError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            # Phase 3 — fire-and-forget 5Y daily-history backfill so the new
            # ticker has chart data within seconds of being added. When no
            # adapter is configured this no-ops silently.
            adapter = _resolve_financial_adapter(request)
            background.add_task(_run_backfill, db_session_factory, dto.ticker, adapter)

            return _dto_to_out(dto)

    @router.patch("/holdings/{holding_id}", response_model=HoldingOut)
    def update_holding(
        holding_id: str, body: HoldingPatch, user: User = require_user
    ) -> HoldingOut:
        data = body.model_dump(exclude_unset=True)
        with _session() as s:
            try:
                dto = svc.update_holding(
                    s,
                    user_id=user.id,
                    holding_id=holding_id,
                    shares=data.get("shares"),
                    cost_basis=data.get("cost_basis"),
                    currency=data.get("currency"),
                    notes=data.get("notes"),
                    groups=data.get("groups"),
                    _patch_shares="shares" in data,
                    _patch_cost="cost_basis" in data,
                    _patch_currency="currency" in data,
                    _patch_notes="notes" in data,
                    _patch_groups="groups" in data,
                )
            except svc.HoldingNotFoundError as exc:
                raise HTTPException(status_code=404, detail="holding not found") from exc
            return _dto_to_out(dto)

    @router.delete("/holdings/{holding_id}", status_code=204)
    def delete_holding(holding_id: str, user: User = require_user) -> Response:
        with _session() as s:
            try:
                svc.delete_holding(s, user_id=user.id, holding_id=holding_id)
            except svc.HoldingNotFoundError as exc:
                raise HTTPException(status_code=404, detail="holding not found") from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/analytics")
    def analytics(
        request: Request,
        market: str | None = None,
        user: User = require_user,
    ) -> dict:
        market_filter = _resolve_market(market)
        with _session() as s:
            holdings = svc.list_holdings(s, user_id=user.id, market=market_filter)
            tickers = [h.ticker for h in holdings]
            quote_rows = quotes_svc.get_quotes_bulk(s, tickers=tickers)
            prices: dict[str, Decimal | None] = {
                t: (quote_rows[t].last_price if t in quote_rows else None)
                for t in (raw.upper() for raw in tickers)
            }
            result = svc.compute_analytics(s, user_id=user.id, prices=prices, market=market_filter)
            last_quote_at = max(
                (r.fetched_at for r in quote_rows.values()),
                default=None,
            )
            display_currency = (
                _MARKET_DISPLAY_CURRENCY[market_filter]
                if market_filter is not None
                else prefs_svc.get_display_currency(s, user_id=user.id)
            )
        currencies_present = {h.currency for h in holdings if h.currency}
        needs_fx = market_filter is None and (
            len(currencies_present) > 1
            or (len(currencies_present) == 1 and display_currency not in currencies_present)
        )
        adapter = _resolve_financial_adapter(request)
        fx_unavailable = needs_fx and adapter is None
        return {
            "last_quote_at": (last_quote_at.isoformat() if last_quote_at is not None else None),
            "display_currency": display_currency,
            "currencies_present": sorted(currencies_present),
            "needs_fx": needs_fx,
            "fx_unavailable": fx_unavailable,
            "total_market_value": str(result.total_market_value),
            "total_cost_basis": str(result.total_cost_basis),
            "total_unrealized_pl": str(result.total_unrealized_pl),
            "total_unrealized_pl_pct": (
                str(result.total_unrealized_pl_pct)
                if result.total_unrealized_pl_pct is not None
                else None
            ),
            "positions": [
                {
                    "holding_id": p.holding_id,
                    "ticker": p.ticker,
                    "shares": str(p.shares) if p.shares is not None else None,
                    "cost_basis": (str(p.cost_basis) if p.cost_basis is not None else None),
                    "last_price": (str(p.last_price) if p.last_price is not None else None),
                    "market_value": (str(p.market_value) if p.market_value is not None else None),
                    "unrealized_pl": (
                        str(p.unrealized_pl) if p.unrealized_pl is not None else None
                    ),
                    "unrealized_pl_pct": (
                        str(p.unrealized_pl_pct) if p.unrealized_pl_pct is not None else None
                    ),
                    "weight": str(p.weight) if p.weight is not None else None,
                    "currency": p.currency,
                }
                for p in result.positions
            ],
            "allocations": {k: str(v) for k, v in result.allocations.items()},
        }

    @router.post("/refresh-prices")
    def refresh_prices(market: str | None = None, user: User = require_user) -> dict:
        from datetime import UTC, datetime

        market_filter = _resolve_market(market)
        remaining = cache.refresh_cooldown_remaining(user.id)
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail={"retry_after": int(remaining) + 1},
            )
        with _session() as s:
            holdings = svc.list_holdings(s, user_id=user.id, market=market_filter)
        provider = provider_factory()
        tickers = [h.ticker for h in holdings]
        # Force-refresh: drop these tickers from the in-memory cache and
        # refetch via the provider. Each fetched price is also upserted into
        # portfolio_quotes so /analytics reflects the new state immediately.
        cache.invalidate(tickers)
        prices = cache.fetch_many(provider, tickers)
        source_id = getattr(provider, "source_id", None) or "unknown"
        now = datetime.now(UTC)
        with _session() as s:
            holdings_by_ticker = {
                h.ticker: h for h in svc.list_holdings(s, user_id=user.id, market=market_filter)
            }
            from openlia_server.db.models.content import PortfolioQuoteIntraday

            for t, price in prices.items():
                if price is None:
                    continue
                quotes_svc.upsert_quote(
                    s,
                    ticker=t,
                    last_price=price,
                    previous_close=None,
                    day_open=None,
                    day_high=None,
                    day_low=None,
                    volume=None,
                    currency=(holdings_by_ticker[t].currency if t in holdings_by_ticker else None),
                    quote_at=now,
                    fetched_at=now,
                    source=source_id,
                )
                s.add(PortfolioQuoteIntraday(ticker=t, ts=now, close=price))
            s.commit()
        cache.mark_refresh(user.id)
        return {"prices": {t: (str(p) if p is not None else None) for t, p in prices.items()}}

    @router.post("/import-csv")
    def import_csv(body: dict, user: User = require_user) -> dict:
        text = body.get("text", "")
        with _session() as s:
            result = svc.import_csv(s, user_id=user.id, text=text)
        return {
            "created": [_dto_to_out(d).model_dump() for d in result.created],
            "errors": result.errors,
        }

    @router.get("/export-csv")
    def export_csv(user: User = require_user) -> Response:
        with _session() as s:
            text = svc.export_csv(s, user_id=user.id)
        return Response(
            content=text,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="portfolio.csv"'},
        )

    @router.get("/search")
    def search(q: str, request: Request, user: User = require_user) -> dict:
        """Adapter-backed ticker lookup over `company_profile`.

        Empty query returns ``[]``. Adapter errors degrade to ``[]`` (no 5xx).
        Rows for tickers already in the user's portfolio carry
        ``already_added: True``.
        """
        q_clean = q.strip().upper()
        if not q_clean:
            return {"results": []}
        adapter = _resolve_financial_adapter(request)
        rows: list[SearchResultOut] = []
        if adapter is not None:
            try:
                result = asyncio.run(adapter.fetch("company_profile", {"symbol": q_clean}))
            except Exception as exc:
                logger.debug("portfolio search fetch failed for %s: %s", q_clean, exc)
                return {"results": []}
            row = _profile_to_search_row(q_clean, getattr(result, "payload", None))
            if row is not None:
                rows.append(row)
        else:
            # No adapter configured: return a minimal stub so the UI can still
            # surface the typed query as a candidate symbol.
            rows.append(SearchResultOut(ticker=q_clean, name=None, exchange=None))
        with _session() as s:
            existing = {h.ticker for h in svc.list_holdings(s, user_id=user.id)}
        for r in rows:
            if r.ticker in existing:
                r.already_added = True
        return {"results": [r.model_dump() for r in rows]}

    # ---------- Groups ------------------------------------------------------

    @router.get("/groups")
    def list_groups(user: User = require_user) -> dict:
        with _session() as s:
            return {"groups": svc.list_groups(s, user_id=user.id)}

    @router.post("/groups", status_code=201)
    def create_group(body: GroupCreateIn, user: User = require_user) -> dict:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        with _session() as s:
            svc.create_group(s, user_id=user.id, name=name)
            return {"groups": svc.list_groups(s, user_id=user.id)}

    @router.patch("/groups/{name}")
    def rename_group(name: str, body: GroupRenameIn, user: User = require_user) -> dict:
        new_name = body.new_name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="new_name is required")
        with _session() as s:
            try:
                svc.rename_group(s, user_id=user.id, old_name=name, new_name=new_name)
            except svc.GroupNotFoundError as exc:
                raise HTTPException(status_code=404, detail="group not found") from exc
            return {"groups": svc.list_groups(s, user_id=user.id)}

    @router.post("/groups/reorder")
    def reorder_groups(body: GroupReorderIn, user: User = require_user) -> dict:
        with _session() as s:
            svc.reorder_groups(s, user_id=user.id, order=body.order)
            return {"groups": svc.list_groups(s, user_id=user.id)}

    @router.delete("/groups/{name}")
    def delete_group(name: str, user: User = require_user) -> dict:
        with _session() as s:
            svc.delete_group(s, user_id=user.id, name=name)
            return {"groups": svc.list_groups(s, user_id=user.id)}

    # ---------- Value series (Phase 3) -------------------------------------

    @router.get("/value-series")
    def value_series(
        timeframe: str = "1m",
        market: str | None = None,
        user: User = require_user,
    ) -> dict:
        from datetime import UTC, datetime

        from openlia_server.services.portfolio_value_series import (
            compute_value_series,
            compute_value_series_intraday,
        )

        market_filter = _resolve_market(market)
        today = datetime.now(UTC).date()
        with _session() as s:
            if timeframe.lower() == "1d":
                result = compute_value_series_intraday(
                    s, user_id=user.id, today=today, market=market_filter
                )
            else:
                result = compute_value_series(
                    s,
                    user_id=user.id,
                    timeframe=timeframe,
                    today=today,
                    market=market_filter,
                )
        return {
            "timeframe": result.timeframe,
            "actual_span": (
                {
                    "start": result.actual_span.start.isoformat(),
                    "end": result.actual_span.end.isoformat(),
                }
                if result.actual_span is not None
                else None
            ),
            "points": [
                {
                    "date": p.date.isoformat(),
                    "value": str(p.value),
                    "ts": p.ts.isoformat() if p.ts is not None else None,
                }
                for p in result.points
            ],
            "period_return_abs": (
                str(result.period_return_abs) if result.period_return_abs is not None else None
            ),
            "period_return_pct": (
                str(result.period_return_pct) if result.period_return_pct is not None else None
            ),
        }

    # ---------- Ticker series (Phase 4) ------------------------------------

    @router.get("/ticker-series")
    def ticker_series(
        timeframe: str = "1d",
        market: str | None = None,
        user: User = require_user,
    ) -> dict:
        from datetime import UTC, datetime

        from openlia_server.services.portfolio_ticker_series import (
            compute_ticker_series,
        )

        market_filter = _resolve_market(market)
        today = datetime.now(UTC).date()
        with _session() as s:
            result = compute_ticker_series(
                s,
                user_id=user.id,
                timeframe=timeframe,
                today=today,
                market=market_filter,
            )
        return {
            "timeframe": result.timeframe,
            "series": {
                ticker: [{"ts": p.ts, "close": str(p.close)} for p in points]
                for ticker, points in result.series.items()
            },
            "period_change_pct": {
                ticker: (str(v) if v is not None else None)
                for ticker, v in result.period_change_pct.items()
            },
        }

    # ---------- Preferences ------------------------------------------------

    @router.get("/prefs", response_model=PrefsOut)
    def get_prefs(user: User = require_user) -> PrefsOut:
        with _session() as s:
            return PrefsOut(
                refresh_cadence=prefs_svc.get_refresh_cadence(s, user_id=user.id),
                display_currency=prefs_svc.get_display_currency(s, user_id=user.id),
            )

    @router.put("/prefs", response_model=PrefsOut)
    def put_prefs(body: PrefsPatchIn, user: User = require_user) -> PrefsOut:
        with _session() as s:
            if body.refresh_cadence is not None:
                try:
                    prefs_svc.set_refresh_cadence(s, user_id=user.id, cadence=body.refresh_cadence)
                except prefs_svc.InvalidCadenceError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            if body.display_currency is not None:
                try:
                    prefs_svc.set_display_currency(
                        s, user_id=user.id, currency=body.display_currency
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            return PrefsOut(
                refresh_cadence=prefs_svc.get_refresh_cadence(s, user_id=user.id),
                display_currency=prefs_svc.get_display_currency(s, user_id=user.id),
            )

    return router
