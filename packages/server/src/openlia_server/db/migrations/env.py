from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import openlia_server.db.models.register_all  # noqa: F401
from openlia_server.db import bootstrap
from openlia_server.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# Tables managed outside the SQLAlchemy metadata graph (e.g. the SQLite
# FTS5 shadow on graph_artifact_summaries and its four internal
# auxiliary tables — created by the slice-10 hybrid retrieval migration
# and by an `after_create` DDL event for tests). Autogenerate must not
# treat their absence in `Base.metadata` as a drop-candidate.
_FTS_SHADOW_TABLES = frozenset(
    {
        "graph_artifact_summaries_fts",
        "graph_artifact_summaries_fts_config",
        "graph_artifact_summaries_fts_data",
        "graph_artifact_summaries_fts_docsize",
        "graph_artifact_summaries_fts_idx",
    }
)


def _include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in _FTS_SHADOW_TABLES:
        return False
    return True


def _db_url() -> str:
    return bootstrap.resolve_db_url()


def run_migrations_offline() -> None:
    url = _db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _db_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_server_default=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
