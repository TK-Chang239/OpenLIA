"""Retail Sentiment department routes.

Compressed surface compared to the full plan: ships dashboard, history,
config GET/PUT, run POST, stocks/{ticker}, spikes GET. Schedule endpoints
are deferred to a follow-up task once JobType.RS_SNAPSHOT ships.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from openlia.retail_sentiment.schemas import MetricSnapshot, SpikeEvent
from openlia.retail_sentiment.spike_detector import detect_spike
from pydantic import BaseModel, Field

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.rs_config import RsConfigService
from openlia_server.services.rs_runner import RsRunner
from openlia_server.services.rs_snapshot import RsSnapshotService


class _ConfigDTO(BaseModel):
    active_tab: str | None = None
    metric_settings: dict[str, Any] | None = None
    filter_presets: list[Any] | None = None
    refresh_interval_minutes: int | None = None


class _RunDTO(BaseModel):
    tickers: list[str] = Field(default_factory=list)


def _snapshot_out(snap: MetricSnapshot) -> dict[str, Any]:
    return {
        "ticker": snap.ticker,
        "captured_at": snap.captured_at.isoformat(),
        "sentiment_score": snap.sentiment_score,
        "buzz_volume": snap.buzz_volume,
        "sentiment_momentum": snap.sentiment_momentum,
        "bull_bear_ratio": snap.bull_bear_ratio,
        "buzz_sentiment_divergence": snap.buzz_sentiment_divergence,
        "social_velocity": snap.social_velocity,
        "cross_source_agreement": snap.cross_source_agreement,
        "put_call_ratio": snap.put_call_ratio,
        "short_interest_pressure": snap.short_interest_pressure,
        "narrative_concentration": snap.narrative_concentration,
        "institutional_retail_gap": snap.institutional_retail_gap,
        "event_sensitivity": snap.event_sensitivity,
        "source_breakdown": dict(snap.source_breakdown),
    }


def _spike_out(spike: SpikeEvent) -> dict[str, Any]:
    return {
        "ticker": spike.ticker,
        "detected_at": spike.detected_at.isoformat(),
        "buzz": spike.buzz,
        "baseline_mean": spike.baseline_mean,
        "baseline_stddev": spike.baseline_stddev,
        "z_score": spike.z_score,
    }


def _config_out(cfg: Any) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "user_id": cfg.user_id,
        "active_tab": cfg.active_tab,
        "metric_settings": cfg.metric_settings,
        "filter_presets": cfg.filter_presets,
        "refresh_interval_minutes": cfg.refresh_interval_minutes,
    }


def build_retail_sentiment_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/departments/retail_sentiment", tags=["retail_sentiment"])

    def _config_svc() -> RsConfigService:
        return RsConfigService(session_factory=db_session_factory)

    def _snap_svc() -> RsSnapshotService:
        return RsSnapshotService(session_factory=db_session_factory)

    def _runner_dep(request: Request) -> RsRunner:
        runner = getattr(request.app.state, "rs_runner", None)
        if runner is None:
            raise HTTPException(status_code=503, detail="retail sentiment runner not wired")
        return runner

    @router.get("/dashboard")
    def get_dashboard(user: User = require_auth) -> dict[str, Any]:
        svc = _snap_svc()
        tickers = svc.all_recent_tickers(days=7)
        latest = svc.latest_many(tickers)
        snapshots = [_snapshot_out(s) for s in latest.values()]
        return {
            "tickers": tickers,
            "snapshots": snapshots,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    @router.get("/dashboard/history")
    def get_history(
        ticker: str,
        days: int = 7,
        user: User = require_auth,
    ) -> dict[str, Any]:
        history = _snap_svc().history(ticker, days=days)
        return {
            "ticker": ticker,
            "snapshots": [_snapshot_out(s) for s in history],
        }

    @router.get("/config")
    def get_config(user: User = require_auth) -> dict[str, Any]:
        return _config_out(_config_svc().get_or_create(user.id))

    @router.put("/config")
    def put_config(payload: _ConfigDTO, user: User = require_auth) -> dict[str, Any]:
        try:
            cfg = _config_svc().update(
                user.id,
                active_tab=payload.active_tab,
                metric_settings=payload.metric_settings,
                filter_presets=payload.filter_presets,
                refresh_interval_minutes=payload.refresh_interval_minutes,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _config_out(cfg)

    @router.post("/run")
    def post_run(
        payload: _RunDTO,
        user: User = require_auth,
        runner: RsRunner = Depends(_runner_dep),
    ) -> dict[str, Any]:
        if not payload.tickers:
            raise HTTPException(400, "tickers required")
        results = runner.run_many(payload.tickers)
        return {
            "snapshots": [
                {
                    "snapshot_id": r.snapshot_id,
                    **_snapshot_out(r.snapshot),
                    "spike": _spike_out(r.spike) if r.spike else None,
                }
                for r in results
            ],
        }

    @router.get("/stocks/{ticker}/sentiment")
    def get_stock(ticker: str, user: User = require_auth) -> dict[str, Any]:
        snap = _snap_svc().latest(ticker)
        if snap is None:
            raise HTTPException(404, f"no snapshot for {ticker}")
        history = _snap_svc().history(ticker, days=7)
        return {
            "latest": _snapshot_out(snap),
            "history": [_snapshot_out(h) for h in history],
        }

    @router.get("/spikes")
    def get_spikes(user: User = require_auth) -> dict[str, Any]:
        svc = _snap_svc()
        tickers = svc.all_recent_tickers(days=7)
        spikes: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for t in tickers:
            latest = svc.latest(t)
            if latest is None:
                continue
            history = svc.history(t, days=7)
            # Exclude the latest row from the baseline window.
            baseline = [h for h in history if h.captured_at < latest.captured_at]
            spike = detect_spike(
                ticker=t,
                detected_at=now,
                current_buzz=latest.buzz_volume,
                recent_snapshots=baseline,
            )
            if spike is not None:
                spikes.append(_spike_out(spike))
        return {"spikes": spikes}

    return router
