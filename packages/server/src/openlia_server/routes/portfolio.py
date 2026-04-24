"""Portfolio routes — CRUD + analytics + CSV + price refresh."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
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
        # Force-refresh: clear these tickers from cache first.
        for h in holdings:
            cache._cache.pop(h.ticker.upper(), None)
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
    def search(q: str, user: User = require_user) -> dict:
        """Minimal ticker search — v1 is a pass-through returning the query.

        A real adapter-backed search is deferred to a follow-up polish pass
        (spec: EODHD symbol-search endpoint).
        """
        q = q.strip().upper()
        if not q:
            return {"results": []}
        return {"results": [{"ticker": q, "name": None}]}

    return router
