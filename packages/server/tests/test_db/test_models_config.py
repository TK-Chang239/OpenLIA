from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.auth
    import openlia_server.db.models.config  # noqa: F401
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_llm_providers_columns(create_tables) -> None:
    from openlia_server.db.models.config import LLMProvider

    cols = {c.name for c in LLMProvider.__table__.columns}
    assert cols == {
        "id",
        "kind",
        "label",
        "api_key",
        "env_var_name",
        "base_url",
        "extra_config",
        "is_enabled",
        "created_at",
        "updated_at",
        "created_by_user_id",
    }


def test_llm_model_has_no_tier_attrs() -> None:
    from openlia_server.db.models.config import LLMModel

    assert not hasattr(LLMModel, "tier")
    assert not hasattr(LLMModel, "is_tier_default")


def test_llm_slot_default_model_exists(create_tables) -> None:
    from openlia_server.db.models.config import LLMSlotDefault

    assert LLMSlotDefault.__tablename__ == "llm_slot_defaults"
    cols = {c.name for c in LLMSlotDefault.__table__.columns}
    assert cols == {"slot_kind", "slot_id", "model_id", "updated_at"}
    pk_cols = {c.name for c in LLMSlotDefault.__table__.primary_key}
    assert pk_cols == {"slot_kind", "slot_id"}


def test_user_llm_preference_removed() -> None:
    import openlia_server.db.models.config as cfg

    assert not hasattr(cfg, "UserLLMPreference")


def test_web_search_providers_priority_default(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.config import WebSearchProvider

    p = WebSearchProvider(id="w1", kind="brave", label="Brave")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.priority == 100
    assert p.is_enabled is True


def test_llm_model_provider_restrict_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    p = LLMProvider(id="p1", kind="openai", label="p")
    m = LLMModel(id="m1", provider_id="p1", model_ref="a", display_name="A")
    db_session.add_all([p, m])
    db_session.commit()

    db_session.delete(p)
    with pytest.raises(IntegrityError):
        db_session.commit()
