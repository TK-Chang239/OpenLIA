import pytest
from openlia.skills import parse_skill_md
from openlia_server.skills.database_store import DatabaseSkillStore

SAMPLE = """---
name: beta
description: Beta skill.
version: "0.1.0"
departments: [secretary]
---

Body.
"""


@pytest.mark.asyncio
async def test_install_then_get(db_session_factory):
    store = DatabaseSkillStore(session_factory=db_session_factory)
    manifest, body = parse_skill_md(SAMPLE)
    await store.install(source="zip", scope="user", user_id="u1", body=body, manifest=manifest)
    got = await store.get("beta", scope="user", user_id="u1")
    assert got is not None
    assert got.manifest.name == "beta"
    assert got.body.strip() == "Body."


@pytest.mark.asyncio
async def test_install_then_uninstall(db_session_factory):
    store = DatabaseSkillStore(session_factory=db_session_factory)
    manifest, body = parse_skill_md(SAMPLE)
    await store.install(source="zip", scope="user", user_id="u1", body=body, manifest=manifest)
    await store.uninstall("beta", scope="user", user_id="u1")
    assert await store.get("beta", scope="user", user_id="u1") is None


@pytest.mark.asyncio
async def test_set_enabled_persists(db_session_factory):
    store = DatabaseSkillStore(session_factory=db_session_factory)
    manifest, body = parse_skill_md(SAMPLE)
    await store.install(source="zip", scope="user", user_id="u1", body=body, manifest=manifest)
    await store.set_enabled("beta", False, scope="user", user_id="u1")
    got = await store.get("beta", scope="user", user_id="u1")
    assert got is not None
    assert got.enabled is False
