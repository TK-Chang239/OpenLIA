"""Slice 10 (hybrid retrieval) — SQLite FTS5 shadow on graph_artifact_summaries.

Creates an FTS5 virtual table that mirrors the four text fields of
``graph_artifact_summaries`` plus three triggers (INSERT/UPDATE/DELETE)
that keep the index in sync using the standard ``external content``
delete-then-insert pattern from SQLite FTS5 docs section 4.4.3.

Postgres is out of scope here — its tsvector path is a different
slice. When the running backend isn't SQLite this migration is a
no-op so Alembic upgrades stay clean across both engines.

Revision ID: 20260511_0200_graph_artifact_summaries_fts
Revises: 20260511_0100_graph_artifact_summary_structured
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260511_0200_graph_artifact_summaries_fts"
down_revision: str | Sequence[str] | None = "20260511_0100_graph_artifact_summary_structured"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FTS_TABLE = "graph_artifact_summaries_fts"
_PARENT = "graph_artifact_summaries"


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if not _is_sqlite():
        # Postgres tsvector path is a separate slice. No-op here.
        return

    op.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE} USING fts5(
            summary_text,
            subject,
            tagline,
            findings_text,
            content='{_PARENT}',
            content_rowid='rowid'
        )
        """
    )

    # Backfill any rows already present in the parent table.
    op.execute(
        f"""
        INSERT INTO {_FTS_TABLE}(rowid, summary_text, subject, tagline, findings_text)
        SELECT rowid, summary_text, subject, tagline, findings_text FROM {_PARENT}
        """
    )

    # External-content sync triggers (SQLite FTS5 docs §4.4.3).
    op.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {_PARENT}_ai
        AFTER INSERT ON {_PARENT} BEGIN
            INSERT INTO {_FTS_TABLE}(rowid, summary_text, subject, tagline, findings_text)
            VALUES (new.rowid, new.summary_text, new.subject, new.tagline, new.findings_text);
        END
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {_PARENT}_ad
        AFTER DELETE ON {_PARENT} BEGIN
            INSERT INTO {_FTS_TABLE}({_FTS_TABLE}, rowid, summary_text, subject, tagline, findings_text)
            VALUES ('delete', old.rowid, old.summary_text, old.subject, old.tagline, old.findings_text);
        END
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {_PARENT}_au
        AFTER UPDATE ON {_PARENT} BEGIN
            INSERT INTO {_FTS_TABLE}({_FTS_TABLE}, rowid, summary_text, subject, tagline, findings_text)
            VALUES ('delete', old.rowid, old.summary_text, old.subject, old.tagline, old.findings_text);
            INSERT INTO {_FTS_TABLE}(rowid, summary_text, subject, tagline, findings_text)
            VALUES (new.rowid, new.summary_text, new.subject, new.tagline, new.findings_text);
        END
        """
    )


def downgrade() -> None:
    if not _is_sqlite():
        return
    op.execute(f"DROP TRIGGER IF EXISTS {_PARENT}_au")
    op.execute(f"DROP TRIGGER IF EXISTS {_PARENT}_ad")
    op.execute(f"DROP TRIGGER IF EXISTS {_PARENT}_ai")
    op.execute(f"DROP TABLE IF EXISTS {_FTS_TABLE}")
