import pytest
from openlia.skills import LayeredSkillStore, SkillStore


class _Dummy:
    async def list(self, *, scope, user_id):
        return []

    async def get(self, skill_id, *, scope, user_id):
        return None

    async def install(self, source, *, scope, user_id, body, manifest): ...

    async def uninstall(self, skill_id, *, scope, user_id): ...

    async def set_enabled(self, skill_id, enabled, *, scope, user_id): ...


def test_protocol_is_runtime_checkable():
    assert isinstance(_Dummy(), SkillStore)


def test_layered_store_routes_by_scope():
    sys_, usr = _Dummy(), _Dummy()
    layered = LayeredSkillStore(system=sys_, user=usr)
    assert layered.for_scope("system") is sys_
    assert layered.for_scope("user") is usr


@pytest.mark.asyncio
async def test_list_visible_combines_scopes():
    layered = LayeredSkillStore(system=_Dummy(), user=_Dummy())
    out = await layered.list_visible(user_id="u1")
    assert out == []  # both stubs return empty


@pytest.mark.asyncio
async def test_list_visible_filters_to_one_scope():
    layered = LayeredSkillStore(system=_Dummy(), user=_Dummy())
    sys_only = await layered.list_visible(user_id="u1", scope_filter="system")
    user_only = await layered.list_visible(user_id="u1", scope_filter="user")
    assert sys_only == []
    assert user_only == []
