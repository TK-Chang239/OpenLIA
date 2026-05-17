"""Resolver must accept a `role` parameter ('flagship' | 'subagent').

When `role="subagent"` is requested but no per-(department, role) pick is
configured, the resolver falls back to the flagship and emits a warning
event the caller can record."""

from __future__ import annotations

import pytest
from openlia.llm.resolver import resolve_role
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel


def _resolved(ref: str) -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id=ref,
        model_ref=ref,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _FakePrefs:
    def __init__(self, picks: dict[tuple[str, str, str], str]) -> None:
        self._picks = picks  # (department_id, user_id, role) -> model_id

    def get_model_pick(self, *, department_id: str, user_id: str | None, role: str) -> str | None:
        return self._picks.get((department_id, user_id or "", role))


class _FakeRegistry:
    def resolve(self, model_id: str) -> ResolvedModel:
        return _resolved(model_id)


def test_explicit_role_pick_resolves() -> None:
    prefs = _FakePrefs({("equity_research", "u_1", "subagent"): "cheap-model"})
    out = resolve_role(
        department_id="equity_research",
        user_id="u_1",
        role="subagent",
        registry=_FakeRegistry(),
        prefs=prefs,
        server_defaults={},
        warn=lambda *a, **k: None,
    )
    assert out.model_ref == "cheap-model"


def test_subagent_falls_back_to_flagship_and_warns() -> None:
    warnings: list[tuple[str, str]] = []
    prefs = _FakePrefs({("equity_research", "u_1", "flagship"): "flagship-model"})
    out = resolve_role(
        department_id="equity_research",
        user_id="u_1",
        role="subagent",
        registry=_FakeRegistry(),
        prefs=prefs,
        server_defaults={},
        warn=lambda cat, msg: warnings.append((cat, msg)),
    )
    assert out.model_ref == "flagship-model"
    assert warnings == [
        (
            "report.warning.subagent_unconfigured",
            "Subagent model not configured; falling back to flagship.",
        )
    ]


def test_flagship_unconfigured_raises() -> None:
    from openlia.llm.exceptions import ModelNotConfiguredError

    prefs = _FakePrefs({})
    with pytest.raises(ModelNotConfiguredError):
        resolve_role(
            department_id="equity_research",
            user_id=None,
            role="flagship",
            registry=_FakeRegistry(),
            prefs=prefs,
            server_defaults={},
            warn=lambda *a, **k: None,
        )


def test_server_default_used_when_no_user_pick() -> None:
    prefs = _FakePrefs({})
    out = resolve_role(
        department_id="equity_research",
        user_id="u_1",
        role="subagent",
        registry=_FakeRegistry(),
        prefs=prefs,
        server_defaults={("equity_research", "subagent"): "default-cheap"},
        warn=lambda *a, **k: None,
    )
    assert out.model_ref == "default-cheap"
