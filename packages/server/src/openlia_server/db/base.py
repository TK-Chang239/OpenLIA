"""SQLAlchemy declarative base + `UTCDateTime` decorator shared across all ORM models.

See `planning/specs/systems/database-design.md` §2 "Portable type conventions"
for the storage contract. `UTCDateTime` keeps datetimes timezone-aware on the
write path so Postgres's `TIMESTAMP WITH TIME ZONE` columns receive aware
values; on read it re-attaches `UTC` when the backing driver (SQLite) returns
naive strings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import (
    DateTime,  # kept for TypeDecorator impl
    MetaData,
    func,
    types,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(types.TypeDecorator):
    """DateTime column type that enforces UTC on write and read.

    On write: aware datetimes are normalized to UTC; naive datetimes pass
    through and are interpreted by the DB as UTC (spec §2 contract is that
    the app layer never writes naive datetimes, but we accept them rather
    than raising since Python stdlib helpers produce naive UTC).

    On read: if the driver returns a naive datetime (SQLite does), we
    re-attach `tzinfo=UTC` so downstream code sees a uniformly aware value.

    The impl type is `DateTime(timezone=True)` so Postgres and other
    tz-aware backends store the offset faithfully.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(UTC)
        return value

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    """Common declarative base for every ORM model in the server.

    Pinned to the project-wide naming convention so index / constraint names
    stay deterministic and Alembic autogenerate produces stable diffs. The
    `type_annotation_map` ensures any `Mapped[datetime]` column uses
    `UTCDateTime` without callers having to remember it.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict] = {
        datetime: UTCDateTime(),
    }


class TimestampMixin:
    """Mixin providing `created_at` and `updated_at` columns.

    Tables that mutate over time should mix this in. Append-only / event
    tables should instead declare `created_at` by hand and omit
    `updated_at` — see `database-design.md` §2 "Timestamps".
    """

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
