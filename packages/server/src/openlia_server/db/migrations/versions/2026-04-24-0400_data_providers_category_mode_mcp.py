"""Phase 3 fix-plan NEW-3-05 — add category, mode, mcp_url, mcp_auth_header
to data_providers, plus CHECK constraints.

Backfills `category='financial'` for existing rows whose `kind` is one of
the financial adapters, `category='news'` for known news adapters, and
defaults to `financial` otherwise. `mode` defaults to `api_key`.

Revision ID: 20260424_0400_dp_category_mcp
Revises: 20260424_0300_checks
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0400_dp_category_mcp"
down_revision: str | Sequence[str] | None = "20260424_0300_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FINANCIAL_KINDS = ("eodhd", "fmp", "finnhub", "yfinance")
_NEWS_KINDS = ("newsapi_ai", "newsapi_org", "mediastack")


def upgrade() -> None:
    with op.batch_alter_table("data_providers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "category",
                sa.String(length=16),
                nullable=False,
                server_default="financial",
            )
        )
        batch_op.add_column(
            sa.Column(
                "mode",
                sa.String(length=16),
                nullable=False,
                server_default="api_key",
            )
        )
        batch_op.add_column(sa.Column("mcp_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("mcp_auth_header", sa.Text(), nullable=True))
        batch_op.create_index("ix_data_providers_category", ["category"])
        batch_op.create_check_constraint(
            "ck_data_providers_category",
            "category IN ('financial', 'news', 'social_media', 'search')",
        )
        batch_op.create_check_constraint(
            "ck_data_providers_mode",
            "mode IN ('api_key', 'mcp')",
        )

    bind = op.get_bind()
    fin_placeholders = ",".join(f"'{k}'" for k in _FINANCIAL_KINDS)
    news_placeholders = ",".join(f"'{k}'" for k in _NEWS_KINDS)
    bind.execute(
        sa.text(f"UPDATE data_providers SET category = 'news' WHERE kind IN ({news_placeholders})")
    )
    bind.execute(
        sa.text(
            f"UPDATE data_providers SET category = 'financial' WHERE kind IN ({fin_placeholders})"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("data_providers", schema=None) as batch_op:
        batch_op.drop_constraint("ck_data_providers_mode", type_="check")
        batch_op.drop_constraint("ck_data_providers_category", type_="check")
        batch_op.drop_index("ix_data_providers_category")
        batch_op.drop_column("mcp_auth_header")
        batch_op.drop_column("mcp_url")
        batch_op.drop_column("mode")
        batch_op.drop_column("category")
