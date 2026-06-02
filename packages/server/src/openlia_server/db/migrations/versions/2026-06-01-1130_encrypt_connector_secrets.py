"""encrypt connector secrets at rest

Revision ID: enc_secrets_0601
Revises: 1c6b0cda0ed9
Create Date: 2026-06-01 11:30:00.000000+00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "enc_secrets_0601"
down_revision: str | Sequence[str] | None = "1c6b0cda0ed9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_plaintext_json(raw: str) -> bool:
    """Plaintext rows are JSON; Fernet tokens are not JSON-parseable."""
    try:
        json.loads(raw)
        return True
    except (ValueError, TypeError):
        return False


def upgrade() -> None:
    from openlia_server.db import secrets_crypto

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, secrets FROM connectors")).fetchall()
    for row_id, raw in rows:
        if not raw:
            continue
        if not _is_plaintext_json(raw):
            continue  # already encrypted (idempotent re-run)
        token = secrets_crypto.encrypt(raw)
        bind.execute(
            sa.text("UPDATE connectors SET secrets = :s WHERE id = :id"),
            {"s": token, "id": row_id},
        )
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.alter_column("secrets", type_=sa.Text(), postgresql_using="secrets::text")


def downgrade() -> None:
    from openlia_server.db import secrets_crypto

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, secrets FROM connectors")).fetchall()
    for row_id, raw in rows:
        if not raw or _is_plaintext_json(raw):
            continue  # already plaintext
        plain = secrets_crypto.decrypt(raw)
        bind.execute(
            sa.text("UPDATE connectors SET secrets = :s WHERE id = :id"),
            {"s": plain, "id": row_id},
        )
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.alter_column("secrets", type_=sa.JSON(), postgresql_using="secrets::json")
