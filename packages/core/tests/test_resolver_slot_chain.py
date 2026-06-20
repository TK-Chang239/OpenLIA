from dataclasses import dataclass, field

import pytest
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.resolver import ResolvedModelRow, resolve, resolve_system_role
from openlia.llm.types import ProviderCredentials


def _row(model_id: str = "M1") -> ResolvedModelRow:
    return ResolvedModelRow(
        model_id=model_id,
        model_ref="m",
        overrides={},
        provider_id="P1",
        provider_kind="openai",
        credentials=ProviderCredentials(api_key="k", base_url=None, env_var_name=None),
        capability_override=None,
    )


@dataclass
class FakeRegistry:
    by_id: dict[str, ResolvedModelRow] = field(default_factory=dict)
    dept_user_override: dict[tuple[str, str], ResolvedModelRow] = field(default_factory=dict)
    dept_slot_default: dict[str, ResolvedModelRow] = field(default_factory=dict)
    system_role_default: dict[str, ResolvedModelRow] = field(default_factory=dict)

    def get_by_id(self, mid: str) -> ResolvedModelRow | None:
        return self.by_id.get(mid)

    def get_department_user_override(
        self, user_id: str, department_id: str
    ) -> ResolvedModelRow | None:
        return self.dept_user_override.get((user_id, department_id))

    def get_department_slot_default(self, department_id: str) -> ResolvedModelRow | None:
        return self.dept_slot_default.get(department_id)

    def get_system_role_default(self, role_id: str) -> ResolvedModelRow | None:
        return self.system_role_default.get(role_id)


def test_model_id_override_wins():
    row = _row("forced")
    reg = FakeRegistry(by_id={"forced": row})
    out = resolve(department_id="secretary", registry=reg, user_id="U", model_id_override="forced")
    assert out.model_id == "forced"


def test_falls_through_to_user_dept_override_when_explicit_pick_missing():
    over = _row("U-dept")
    reg = FakeRegistry(dept_user_override={("U", "secretary"): over})
    out = resolve(department_id="secretary", registry=reg, user_id="U", model_id_override="ghost")
    assert out.model_id == "U-dept"


def test_user_dept_override_wins_over_slot_default():
    over = _row("U-dept")
    default = _row("D")
    reg = FakeRegistry(
        dept_user_override={("U", "secretary"): over},
        dept_slot_default={"secretary": default},
    )
    out = resolve(department_id="secretary", registry=reg, user_id="U")
    assert out.model_id == "U-dept"


def test_slot_default_used_when_no_user_override():
    default = _row("D")
    reg = FakeRegistry(dept_slot_default={"secretary": default})
    out = resolve(department_id="secretary", registry=reg, user_id="U")
    assert out.model_id == "D"


def test_no_chain_match_raises_model_not_configured():
    reg = FakeRegistry()
    with pytest.raises(ModelNotConfiguredError) as ei:
        resolve(department_id="secretary", registry=reg, user_id="U")
    assert ei.value.slot_kind == "department"
    assert ei.value.slot_id == "secretary"


def test_resolve_system_role_uses_system_role_default():
    default = _row("R")
    reg = FakeRegistry(system_role_default={"graph_extraction": default})
    out = resolve_system_role(role_id="graph_extraction", registry=reg)
    assert out.model_id == "R"


def test_resolve_system_role_missing_raises():
    reg = FakeRegistry()
    with pytest.raises(ModelNotConfiguredError) as ei:
        resolve_system_role(role_id="graph_extraction", registry=reg)
    assert ei.value.slot_kind == "system_role"
    assert ei.value.slot_id == "graph_extraction"
