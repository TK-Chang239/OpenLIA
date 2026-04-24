"""Panic Thermometer user-config + preset service."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openlia.panic_thermometer.panels import PANELS
from openlia.panic_thermometer.presets import PT_PRESETS
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import PtPreset, PtUserConfig

_REQUIRED_PANELS = {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}


def _default_panel_config() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for panel_id, panel in PANELS.items():
        rs = panel.default_ruleset
        out.append(
            {
                "panel_id": panel_id,
                "rules": rs["rules"],
                "params": dict(rs["params"]),
                "streak_condition": rs.get("streak_condition"),
                "manual_override": None,
                "milestone_date": None,
                "enabled": True,
            }
        )
    return out


def _default_composite_settings() -> dict[str, Any]:
    return {
        "mode": "count",
        "red_threshold": 2,
        "weights": {
            "oil": 1.0,
            "inflation": 1.0,
            "fed_language": 0.8,
            "wage_growth": 1.0,
            "diplomacy": 0.5,
        },
        "thresholds": {
            "elevated": 1.0,
            "high": 2.0,
            "severe": 3.0,
            "crisis": 4.0,
        },
    }


@dataclass
class PtConfigService:
    session_factory: Callable[[], Session]

    def _session(self) -> Session:
        return self.session_factory()

    def get_or_create_for_user(self, user_id: str) -> PtUserConfig:
        s = self._session()
        existing = s.query(PtUserConfig).filter_by(user_id=user_id).one_or_none()
        if existing is not None:
            return existing
        row = PtUserConfig(
            id=str(uuid.uuid4()),
            user_id=user_id,
            active_preset_id=None,
            panel_config=_default_panel_config(),
            composite_settings=_default_composite_settings(),
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    def update_config(
        self,
        user_id: str,
        *,
        panel_config: list[dict[str, Any]],
        composite_settings: dict[str, Any],
    ) -> PtUserConfig:
        row = self.get_or_create_for_user(user_id)
        s = self._session()
        row.panel_config = panel_config
        row.composite_settings = composite_settings
        row.active_preset_id = None
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    def seed_shipped_presets(self) -> None:
        """Idempotently insert one PtPreset per (panel, preset_name) pair."""
        s = self._session()
        existing_names = {
            r.name
            for r in s.query(PtPreset)
            .filter(PtPreset.is_shipped.is_(True), PtPreset.user_id.is_(None))
            .all()
        }
        inserted = 0
        for panel_id, presets in PT_PRESETS.items():
            for preset_name, rs in presets.items():
                full_name = f"{panel_id}::{preset_name}"
                if full_name in existing_names:
                    continue
                row = PtPreset(
                    id=str(uuid.uuid4()),
                    user_id=None,
                    name=full_name,
                    description=f"Shipped library: {panel_id} / {preset_name}",
                    is_shipped=True,
                    panel_config=[
                        {
                            "panel_id": panel_id,
                            "rules": rs["rules"],
                            "params": dict(rs["params"]),
                            "streak_condition": rs.get("streak_condition"),
                            "manual_override": None,
                            "milestone_date": None,
                            "enabled": True,
                        }
                    ],
                    composite_settings={},
                )
                s.add(row)
                inserted += 1
        if inserted:
            s.commit()

    def list_presets(self, user_id: str) -> list[PtPreset]:
        s = self._session()
        return (
            s.query(PtPreset)
            .filter((PtPreset.user_id == user_id) | (PtPreset.user_id.is_(None)))
            .order_by(PtPreset.is_shipped.desc(), PtPreset.name)
            .all()
        )

    def create_preset(self, user_id: str, *, name: str, description: str | None) -> PtPreset:
        cfg = self.get_or_create_for_user(user_id)
        s = self._session()
        row = PtPreset(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            is_shipped=False,
            panel_config=cfg.panel_config,
            composite_settings=cfg.composite_settings,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    def update_preset(
        self,
        user_id: str,
        preset_id: str,
        *,
        name: str,
        description: str | None,
    ) -> PtPreset:
        s = self._session()
        row = s.query(PtPreset).filter_by(id=preset_id, user_id=user_id).one_or_none()
        if row is None:
            raise ValueError(f"preset {preset_id} not found for user {user_id}")
        row.name = name
        row.description = description
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    def delete_preset(self, user_id: str, preset_id: str) -> None:
        s = self._session()
        row = s.query(PtPreset).filter_by(id=preset_id, user_id=user_id).one_or_none()
        if row is None:
            raise ValueError(f"preset {preset_id} not found for user {user_id}")
        s.delete(row)
        s.commit()

    def apply_preset(self, user_id: str, preset_id: str) -> PtUserConfig:
        """Load a preset's panel config, merging per-panel into the user's live config.

        Shipped presets carry exactly one panel's config; we merge by panel_id.
        User presets carry the full 5-panel snapshot; we overwrite wholesale.
        """
        s = self._session()
        preset = (
            s.query(PtPreset)
            .filter(
                PtPreset.id == preset_id,
                (PtPreset.user_id == user_id) | (PtPreset.user_id.is_(None)),
            )
            .one_or_none()
        )
        if preset is None:
            raise ValueError(f"preset {preset_id} not found")
        cfg = self.get_or_create_for_user(user_id)
        current = {p["panel_id"]: p for p in cfg.panel_config}
        for incoming in preset.panel_config:
            current[incoming["panel_id"]] = incoming
        cfg.panel_config = [
            current[pid] for pid in ("oil", "inflation", "fed_language", "wage_growth", "diplomacy")
        ]
        if preset.composite_settings:
            cfg.composite_settings = preset.composite_settings
        cfg.active_preset_id = preset.id
        s.add(cfg)
        s.commit()
        s.refresh(cfg)
        return cfg

    def export_config(self, user_id: str) -> dict[str, Any]:
        cfg = self.get_or_create_for_user(user_id)
        return {
            "version": 1,
            "panel_config": cfg.panel_config,
            "composite_settings": cfg.composite_settings,
        }

    def import_config(self, user_id: str, payload: dict[str, Any]) -> PtUserConfig:
        version = payload.get("version")
        if version != 1:
            raise ValueError(f"unsupported PT config version: {version!r}")
        panel_config = payload.get("panel_config") or []
        seen = {p.get("panel_id") for p in panel_config}
        if seen != _REQUIRED_PANELS:
            raise ValueError(
                "panel_config must contain all 5 panels: " + ", ".join(sorted(_REQUIRED_PANELS))
            )
        return self.update_config(
            user_id,
            panel_config=panel_config,
            composite_settings=payload.get("composite_settings") or {},
        )
