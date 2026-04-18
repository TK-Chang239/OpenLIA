from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401
    import openlia_server.db.models.config  # noqa: F401

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_llm_providers_columns(create_tables) -> None:
    from openlia_server.db.models.config import LLMProvider

    cols = {c.name for c in LLMProvider.__table__.columns}
    assert cols == {
        "id", "kind", "label", "api_key_encrypted", "env_var_name", "base_url",
        "extra_config", "is_enabled", "created_at", "updated_at", "created_by_user_id",
    }


def test_llm_models_tier_default_partial_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.config import LLMModel, LLMProvider

    p = LLMProvider(id="p1", kind="openai", label="p")
    db_session.add(p)
    db_session.commit()

    db_session.add(LLMModel(id="m1", provider_id="p1", tier="thinking",
                            model_ref="a", display_name="A", is_tier_default=True))
    db_session.commit()
    db_session.add(LLMModel(id="m2", provider_id="p1", tier="thinking",
                            model_ref="b", display_name="B", is_tier_default=True))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_llm_preferences_composite_pk(create_tables) -> None:
    from openlia_server.db.models.config import UserLLMPreference

    pk_cols = {c.name for c in UserLLMPreference.__table__.primary_key}
    assert pk_cols == {"user_id", "tier"}


def test_data_provider_requirement_mapping_composite_pk(create_tables) -> None:
    from openlia_server.db.models.config import DataProviderRequirementMapping

    pk_cols = {c.name for c in DataProviderRequirementMapping.__table__.primary_key}
    assert pk_cols == {"requirement_type", "provider_id"}


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
    m = LLMModel(id="m1", provider_id="p1", tier="thinking", model_ref="a", display_name="A")
    db_session.add_all([p, m])
    db_session.commit()

    db_session.delete(p)
    with pytest.raises(IntegrityError):
        db_session.commit()
