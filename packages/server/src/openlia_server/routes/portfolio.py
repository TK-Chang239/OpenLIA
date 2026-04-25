"""Portfolio routes — CRUD + analytics + CSV + price refresh + groups + search."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import portfolio as svc
from openlia_server.services.portfolio_prices import (
    PortfolioPriceProvider,
    PriceCache,
    get_default_cache,
    get_default_provider,
)

logger = logging.getLogger(__name__)


class HoldingIn(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})
    ticker: str
    shares: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = "USD"
    notes: str | None = None
    groups: list[str] | None = None


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
    def list_holdings(user: User = require_user) -> list[HoldingOut]:
        with _session() as s:
            return [_dto_to_out(d) for d in svc.list_holdings(s, user_id=user.id)]

    @router.post("/holdings", response_model=HoldingOut, status_code=201)
    def create_holding(body: HoldingIn, user: User = require_user) -> HoldingOut:
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
                )
            except svc.DuplicateTickerError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    def analytics(user: User = require_user) -> dict:
        with _session() as s:
            holdings = svc.list_holdings(s, user_id=user.id)
            tickers = [h.ticker for h in holdings]
            provider = provider_factory()
            prices = cache.fetch_many(provider, tickers)
            result = svc.compute_analytics(s, user_id=user.id, prices=prices)
        return {
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
    def refresh_prices(user: User = require_user) -> dict:
        remaining = cache.refresh_cooldown_remaining(user.id)
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail={"retry_after": int(remaining) + 1},
            )
        with _session() as s:
            holdings = svc.list_holdings(s, user_id=user.id)
        provider = provider_factory()
        # Force-refresh: drop these tickers from the cache via the public API.
        cache.invalidate([h.ticker for h in holdings])
        prices = cache.fetch_many(provider, [h.ticker for h in holdings])
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

    return router
