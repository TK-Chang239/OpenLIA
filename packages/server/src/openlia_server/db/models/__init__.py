"""SQLAlchemy models for the server.

Importing this package registers every model on Base.metadata. Alembic's
env.py and the bootstrap routine rely on this side effect.
"""

from openlia_server.db.models import auth, config, content, infrastructure

__all__ = ["auth", "config", "content", "infrastructure"]
