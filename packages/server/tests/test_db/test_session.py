from __future__ import annotations

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def test_base_has_naming_convention() -> None:
    from openlia_server.db.base import Base

    expected_keys = {"ix", "uq", "ck", "fk", "pk"}
    assert set(Base.metadata.naming_convention.keys()) == expected_keys


def test_timestamp_mixin_columns_present() -> None:
    from openlia_server.db.base import Base, TimestampMixin

    class _Demo(Base, TimestampMixin):
        __tablename__ = "_demo"
        id: Mapped[int] = mapped_column(primary_key=True)

    cols = {c.name: c for c in _Demo.__table__.columns}
    assert "created_at" in cols
    assert "updated_at" in cols
    assert isinstance(cols["created_at"].type, DateTime)
    assert cols["created_at"].type.timezone is True
    assert cols["updated_at"].type.timezone is True
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False
