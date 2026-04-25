from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class WizardState(Base):
    __tablename__ = "wizard_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    current_step: Mapped[str] = mapped_column(String(32), nullable=False, default="mode")
    completed_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    step_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active_session_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'completed')",
            name="status_enum",
        ),
    )


class ConfigStore(Base):
    __tablename__ = "config_store"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
