"""merge eu_v2 and report_v3_instructions heads

Two migrations branched from the same parent (c1e3a7d9f2b4) and reached
``main`` without an Alembic merge, leaving two heads
(``eae15acd2745`` earnings-update-v2 tables and ``d2f4b6a8c0e1``
report_v3.instructions_id). This no-op merge rejoins them into a single
head; both branches already created their own tables.

Revision ID: 79187a917367
Revises: eae15acd2745, d2f4b6a8c0e1
Create Date: 2026-05-31 15:40:17.254834+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "79187a917367"
down_revision: str | Sequence[str] | None = ("eae15acd2745", "d2f4b6a8c0e1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
