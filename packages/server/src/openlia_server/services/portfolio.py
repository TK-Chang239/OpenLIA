"""Portfolio holdings service — CRUD + groups + analytics + reference helper.

Groups are stored as a JSON blob inside `notes` to avoid a schema migration.
When notes is a JSON object of the shape ``{"groups": [...], "text": "..."}``
we treat it as structured; otherwise free text is preserved under
``notes_text`` and no groups are surfaced.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TypedDict

from sqlalchemy.orm import Session

from openlia_server.db.models.content import PortfolioHolding
from openlia_server.services.market_hours import Market, classify_market


class DuplicateTickerError(ValueError):
    """Raised when attempting to insert a duplicate (user_id, ticker)."""


class HoldingNotFoundError(LookupError):
    """Raised when a holding does not exist for the given user."""


class GroupNotFoundError(LookupError):
    """Raised when a group rename targets a non-existent group."""


# Reserved sentinel used to persist user-visible group ordering and
# empty groups inside a hidden PortfolioHolding row.
_GROUPS_META_TICKER = "__GROUPS__"


@dataclass(frozen=True)
class HoldingDTO:
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


class ReferenceHolding(TypedDict):
    ticker: str
    name: str | None
    shares: Decimal | None
    currency: str


def _decode_notes(raw: str | None) -> tuple[list[str], str | None]:
    if raw is None or raw == "":
        return [], None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return [], raw
    if not isinstance(parsed, dict):
        return [], raw
    groups_raw = parsed.get("groups", [])
    groups = [str(g) for g in groups_raw] if isinstance(groups_raw, list) else []
    text = parsed.get("text")
    notes_text = str(text) if text else None
    return groups, notes_text


def _encode_notes(groups: list[str] | None, notes_text: str | None) -> str | None:
    groups = [g for g in (groups or []) if g]
    if not groups and not notes_text:
        return None
    return json.dumps({"groups": groups, "text": notes_text or ""}, sort_keys=True)


def _row_to_dto(row: PortfolioHolding) -> HoldingDTO:
    groups, notes_text = _decode_notes(row.notes)
    return HoldingDTO(
        id=row.id,
        ticker=row.ticker,
        name=row.name,
        shares=row.shares,
        cost_basis=row.cost_basis,
        currency=row.currency,
        groups=groups,
        notes_text=notes_text,
        added_at=row.added_at.isoformat() if row.added_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def create_holding(
    session: Session,
    *,
    user_id: str,
    ticker: str,
    shares: Decimal | None,
    cost_basis: Decimal | None,
    currency: str | None,
    notes: str | None,
    groups: list[str] | None,
    added_at: datetime | None = None,
) -> HoldingDTO:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    if ticker == _GROUPS_META_TICKER:
        raise ValueError("reserved ticker")
    existing = (
        session.query(PortfolioHolding).filter_by(user_id=user_id, ticker=ticker).one_or_none()
    )
    if existing is not None:
        raise DuplicateTickerError(f"{ticker} already exists")
    row = PortfolioHolding(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=ticker,
        name=None,
        shares=shares,
        cost_basis=cost_basis,
        currency=(currency or "USD").upper(),
        notes=_encode_notes(groups, notes),
    )
    if added_at is not None:
        row.added_at = added_at
    session.add(row)
    session.commit()
    session.refresh(row)
    return _row_to_dto(row)


def list_holdings(
    session: Session, *, user_id: str, market: Market | None = None
) -> list[HoldingDTO]:
    rows = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id)
        .order_by(PortfolioHolding.ticker.asc())
        .all()
    )
    dtos = [_row_to_dto(r) for r in rows if r.ticker != _GROUPS_META_TICKER]
    if market is None:
        return dtos
    return [d for d in dtos if classify_market(d.ticker) == market]


def get_holding(session: Session, *, user_id: str, holding_id: str) -> HoldingDTO:
    row = session.query(PortfolioHolding).filter_by(user_id=user_id, id=holding_id).one_or_none()
    if row is None:
        raise HoldingNotFoundError("holding not found")
    return _row_to_dto(row)


def update_holding(
    session: Session,
    *,
    user_id: str,
    holding_id: str,
    shares: Decimal | None = None,
    cost_basis: Decimal | None = None,
    currency: str | None = None,
    notes: str | None = None,
    groups: list[str] | None = None,
    _patch_shares: bool = False,
    _patch_cost: bool = False,
    _patch_currency: bool = False,
    _patch_notes: bool = False,
    _patch_groups: bool = False,
) -> HoldingDTO:
    row = session.query(PortfolioHolding).filter_by(user_id=user_id, id=holding_id).one_or_none()
    if row is None:
        raise HoldingNotFoundError("holding not found")
    if _patch_shares:
        row.shares = shares
    if _patch_cost:
        row.cost_basis = cost_basis
    if _patch_currency and currency:
        row.currency = currency.upper()
    existing_groups, existing_text = _decode_notes(row.notes)
    new_groups = groups if _patch_groups else existing_groups
    new_text = notes if _patch_notes else existing_text
    if _patch_groups or _patch_notes:
        row.notes = _encode_notes(new_groups, new_text)
    session.commit()
    session.refresh(row)
    return _row_to_dto(row)


def delete_holding(session: Session, *, user_id: str, holding_id: str) -> None:
    row = session.query(PortfolioHolding).filter_by(user_id=user_id, id=holding_id).one_or_none()
    if row is None:
        raise HoldingNotFoundError("holding not found")
    session.delete(row)
    session.commit()


# ---------- Groups ------------------------------------------------------------


def _get_groups_meta(session: Session, *, user_id: str) -> list[str]:
    row = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id, ticker=_GROUPS_META_TICKER)
        .one_or_none()
    )
    if row is None or row.notes is None:
        return []
    try:
        parsed = json.loads(row.notes)
    except (ValueError, TypeError):
        return []
    if isinstance(parsed, dict):
        order = parsed.get("order", [])
        if isinstance(order, list):
            return [str(g) for g in order]
    return []


def _set_groups_meta(session: Session, *, user_id: str, order: list[str]) -> None:
    deduped: list[str] = []
    seen: set[str] = set()
    for name in order:
        if name and name not in seen:
            seen.add(name)
            deduped.append(name)
    payload = json.dumps({"order": deduped}, sort_keys=True)
    row = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id, ticker=_GROUPS_META_TICKER)
        .one_or_none()
    )
    if row is None:
        row = PortfolioHolding(
            id=str(uuid.uuid4()),
            user_id=user_id,
            ticker=_GROUPS_META_TICKER,
            name=None,
            shares=None,
            cost_basis=None,
            currency="USD",
            notes=payload,
        )
        session.add(row)
    else:
        row.notes = payload
    session.commit()


def list_groups(session: Session, *, user_id: str) -> list[str]:
    """Return the ordered list of user-visible groups.

    Order = persisted meta order (when present), then any newly-discovered
    groups from holding membership appended in alpha order.
    """
    persisted = _get_groups_meta(session, user_id=user_id)
    seen = set(persisted)
    discovered: set[str] = set()
    for h in list_holdings(session, user_id=user_id):
        for g in h.groups:
            if g and g not in seen:
                discovered.add(g)
    return list(persisted) + sorted(discovered)


def create_group(session: Session, *, user_id: str, name: str) -> list[str]:
    name = name.strip()
    if not name:
        raise ValueError("name is required")
    current = list_groups(session, user_id=user_id)
    if name not in current:
        current.append(name)
    _set_groups_meta(session, user_id=user_id, order=current)
    return current


def rename_group(session: Session, *, user_id: str, old_name: str, new_name: str) -> list[str]:
    old_name = old_name.strip()
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("new_name is required")
    current = list_groups(session, user_id=user_id)
    if old_name not in current:
        raise GroupNotFoundError(f"group {old_name!r} not found")
    # Update every holding that references old_name in a single transaction.
    rows = session.query(PortfolioHolding).filter_by(user_id=user_id).all()
    for row in rows:
        if row.ticker == _GROUPS_META_TICKER:
            continue
        groups, text = _decode_notes(row.notes)
        if old_name in groups:
            new_groups = [new_name if g == old_name else g for g in groups]
            row.notes = _encode_notes(new_groups, text)
    new_order = [new_name if g == old_name else g for g in current]
    payload = json.dumps({"order": new_order}, sort_keys=True)
    meta = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id, ticker=_GROUPS_META_TICKER)
        .one_or_none()
    )
    if meta is None:
        meta = PortfolioHolding(
            id=str(uuid.uuid4()),
            user_id=user_id,
            ticker=_GROUPS_META_TICKER,
            name=None,
            shares=None,
            cost_basis=None,
            currency="USD",
            notes=payload,
        )
        session.add(meta)
    else:
        meta.notes = payload
    session.commit()
    return new_order


def reorder_groups(session: Session, *, user_id: str, order: list[str]) -> list[str]:
    existing = set(list_groups(session, user_id=user_id))
    cleaned = [name for name in order if name in existing]
    # Append any existing groups not present in the supplied order so reorder
    # is non-destructive when partial.
    for name in sorted(existing - set(cleaned)):
        cleaned.append(name)
    _set_groups_meta(session, user_id=user_id, order=cleaned)
    return cleaned


def delete_group(session: Session, *, user_id: str, name: str) -> list[str]:
    name = name.strip()
    rows = session.query(PortfolioHolding).filter_by(user_id=user_id).all()
    for row in rows:
        if row.ticker == _GROUPS_META_TICKER:
            continue
        groups, text = _decode_notes(row.notes)
        if name in groups:
            new_groups = [g for g in groups if g != name]
            row.notes = _encode_notes(new_groups, text)
    current = [g for g in list_groups(session, user_id=user_id) if g != name]
    _set_groups_meta(session, user_id=user_id, order=current)
    return current


def get_reference_holdings(session: Session, *, user_id: str) -> list[ReferenceHolding]:
    """Cross-plan helper consumed by Morning Briefing (Plan 16).

    Returns a minimal holdings list for the Reference Portfolio toggle.
    """
    rows = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id)
        .order_by(PortfolioHolding.ticker.asc())
        .all()
    )
    return [
        ReferenceHolding(
            ticker=r.ticker,
            name=r.name,
            shares=r.shares,
            currency=r.currency,
        )
        for r in rows
        if r.ticker != _GROUPS_META_TICKER
    ]


# ---------- Analytics ---------------------------------------------------------


@dataclass(frozen=True)
class PositionAnalytic:
    holding_id: str
    ticker: str
    shares: Decimal | None
    cost_basis: Decimal | None
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pl: Decimal | None
    unrealized_pl_pct: Decimal | None
    weight: Decimal | None
    currency: str
    previous_close: Decimal | None = None
    day_change_abs: Decimal | None = None
    day_change_pct: Decimal | None = None


@dataclass(frozen=True)
class AnalyticsSummary:
    total_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_pl: Decimal
    total_unrealized_pl_pct: Decimal | None
    positions: list[PositionAnalytic]
    allocations: dict[str, Decimal]  # ticker -> weight (0..1)


def compute_analytics(
    session: Session,
    *,
    user_id: str,
    prices: dict[str, Decimal | None],
    market: Market | None = None,
    previous_closes: dict[str, Decimal | None] | None = None,
) -> AnalyticsSummary:
    """Compute totals, per-position P&L, and allocation weights.

    `prices` is a caller-provided map of ticker -> last_price (or None).
    `previous_closes` is the same shape, providing the prior-session close
    used to derive per-position day-change fields. When omitted, day-change
    fields are null. When `market` is set, only holdings of that market
    contribute.
    """
    rows = list_holdings(session, user_id=user_id, market=market)
    positions_raw: list[tuple[HoldingDTO, Decimal | None, Decimal | None, Decimal | None]] = []
    total_mv = Decimal("0")
    total_cost = Decimal("0")

    for dto in rows:
        last = prices.get(dto.ticker)
        mv: Decimal | None = None
        cost_total: Decimal | None = None
        pl: Decimal | None = None
        if dto.shares is not None and last is not None:
            mv = (dto.shares * last).quantize(Decimal("0.0001"))
            total_mv += mv
        if dto.shares is not None and dto.cost_basis is not None:
            cost_total = (dto.shares * dto.cost_basis).quantize(Decimal("0.0001"))
            total_cost += cost_total
        if mv is not None and cost_total is not None:
            pl = (mv - cost_total).quantize(Decimal("0.0001"))
        positions_raw.append((dto, mv, cost_total, pl))

    allocations: dict[str, Decimal] = {}
    positions: list[PositionAnalytic] = []
    for dto, mv, cost_total, pl in positions_raw:
        weight: Decimal | None = None
        if mv is not None and total_mv > 0:
            weight = (mv / total_mv).quantize(Decimal("0.000001"))
            allocations[dto.ticker] = weight
        pl_pct: Decimal | None = None
        if pl is not None and cost_total is not None and cost_total != 0:
            pl_pct = (pl / cost_total).quantize(Decimal("0.000001"))
        last = prices.get(dto.ticker)
        prev = previous_closes.get(dto.ticker) if previous_closes else None
        day_abs: Decimal | None = None
        day_pct: Decimal | None = None
        if last is not None and prev is not None and prev != 0:
            per_share = last - prev
            if dto.shares is not None:
                day_abs = (per_share * dto.shares).quantize(Decimal("0.0001"))
            day_pct = (per_share / prev).quantize(Decimal("0.000001"))
        positions.append(
            PositionAnalytic(
                holding_id=dto.id,
                ticker=dto.ticker,
                shares=dto.shares,
                cost_basis=dto.cost_basis,
                last_price=last,
                market_value=mv,
                unrealized_pl=pl,
                unrealized_pl_pct=pl_pct,
                weight=weight,
                currency=dto.currency,
                previous_close=prev,
                day_change_abs=day_abs,
                day_change_pct=day_pct,
            )
        )

    total_pl = total_mv - total_cost
    total_pl_pct: Decimal | None = None
    if total_cost > 0:
        total_pl_pct = (total_pl / total_cost).quantize(Decimal("0.000001"))

    return AnalyticsSummary(
        total_market_value=total_mv.quantize(Decimal("0.0001")),
        total_cost_basis=total_cost.quantize(Decimal("0.0001")),
        total_unrealized_pl=total_pl.quantize(Decimal("0.0001")),
        total_unrealized_pl_pct=total_pl_pct,
        positions=positions,
        allocations=allocations,
    )


# ---------- CSV import / export -----------------------------------------------


_CSV_COLUMNS = ("ticker", "shares", "cost_basis", "currency", "notes")


@dataclass(frozen=True)
class CsvImportResult:
    created: list[HoldingDTO]
    errors: list[dict[str, str]]


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal: {value}") from exc


def import_csv(session: Session, *, user_id: str, text: str) -> CsvImportResult:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return CsvImportResult(created=[], errors=[{"row": "0", "error": "empty csv"}])
    # Normalize headers case-insensitively.
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
    if "ticker" not in reader.fieldnames:
        return CsvImportResult(
            created=[], errors=[{"row": "0", "error": "missing 'ticker' column"}]
        )

    created: list[HoldingDTO] = []
    errors: list[dict[str, str]] = []
    for idx, raw in enumerate(reader, start=1):
        try:
            dto = create_holding(
                session,
                user_id=user_id,
                ticker=(raw.get("ticker") or "").strip(),
                shares=_decimal_or_none(raw.get("shares")),
                cost_basis=_decimal_or_none(raw.get("cost_basis")),
                currency=(raw.get("currency") or "USD").strip() or "USD",
                notes=(raw.get("notes") or None),
                groups=None,
            )
            created.append(dto)
        except DuplicateTickerError as exc:
            errors.append({"row": str(idx), "error": str(exc)})
        except ValueError as exc:
            errors.append({"row": str(idx), "error": str(exc)})
    return CsvImportResult(created=created, errors=errors)


def export_csv(session: Session, *, user_id: str) -> str:
    rows = list_holdings(session, user_id=user_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([*_CSV_COLUMNS, "added_at"])
    for dto in rows:
        writer.writerow(
            [
                dto.ticker,
                str(dto.shares) if dto.shares is not None else "",
                str(dto.cost_basis) if dto.cost_basis is not None else "",
                dto.currency,
                dto.notes_text or "",
                dto.added_at,
            ]
        )
    return buf.getvalue()
