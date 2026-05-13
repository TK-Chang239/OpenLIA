"""Alembic round-trip: upgrade to head, then downgrade to base."""

from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy import create_engine, inspect

REPO_ROOT_SERVER = Path(__file__).resolve().parents[2]  # packages/server

EXPECTED_TABLES = {
    # --- Plan 1A baseline (22 tables) ---
    # Auth (6)
    "users",
    "sessions",
    "signup_invites",
    "signup_policy",
    "password_reset_requests",
    "auth_events",
    # Config (6)
    "llm_providers",
    "llm_models",
    "llm_slot_defaults",
    "web_search_providers",
    # Content (8)
    "chat_sessions",
    "chat_messages",
    "chat_attachments",
    "reports",
    "report_versions",
    "portfolio_holdings",
    "watchlists",
    "watchlist_items",
    # Infrastructure (2)
    "wizard_state",
    "config_store",
    # --- Plan 1B additions (11 tables) ---
    # Dashboard (7)
    "pt_user_configs",
    "pt_presets",
    "mr_dashboard_state",
    "mr_assessment_cache",
    "rs_user_config",
    "rs_snapshots",
    "rs_classification_log",
    "fe_saved_formulas",
    # Scheduler + notifications (4)
    "mb_schedules",
    "eu_schedules",
    "rs_schedules",
    "job_runs",
    "user_notifications",
    # --- Plan 11 additions ---
    "user_prefs",
    # --- Plan 12 blockers ---
    "repo_items",
    # --- Plan 14 Equity Research ---
    "er_user_configs",
    # --- Plan 15 Earnings Update ---
    "eu_watchlist",
    "eu_user_configs",
    # --- Plan 16 Morning Briefing ---
    "mb_user_configs",
    # --- Plan 18 Panic Thermometer transition log ---
    "pt_trigger_events",
    # --- Connector redesign (replaces data_providers + data_provider_requirement_mapping) ---
    "connectors",
    "runner_callable_specs",
    # --- Resolver redesign Phase 1 (audit tables) ---
    "resolver_call_log",
    "smoke_call_log",
    # --- Lia Safety & Compliance Guardrails (MVP) ---
    "lia_guardrail_events",
    "user_disclaimer_acceptance",
    # --- Skills MVP (PR #91) ---
    "skills",
    "skill_user_overrides",
    # --- Report tool cache (per-(user, dept) warm-up + usage log) ---
    "report_tool_warmup",
    "report_tool_usage",
    # --- Per-(user, dept) model preference (model picker) ---
    "user_department_model_prefs",
    # --- Cross-session memory graph (slice 1) ---
    "graph_entities",
    "graph_edges",
    # --- Cross-session memory graph (slice 5) ---
    "graph_user_constructs",
    # --- Cross-session memory graph (slice 6) ---
    "graph_extraction_proposals",
    # --- Cross-session memory graph (slice 10) ---
    "graph_artifact_summaries",
    # --- Graph memory runtime spec (slice 4) ---
    "graph_extraction_runs",
    # --- Graph memory runtime spec (slice 10 hybrid retrieval) ---
    # SQLite FTS5 virtual table + four internal shadow tables it manages.
    "graph_artifact_summaries_fts",
    "graph_artifact_summaries_fts_config",
    "graph_artifact_summaries_fts_data",
    "graph_artifact_summaries_fts_docsize",
    "graph_artifact_summaries_fts_idx",
    # --- Portfolio live data (Phase 1) ---
    "portfolio_quotes",
    "portfolio_quote_intraday",
    "portfolio_quote_daily",
}


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    import os

    merged = os.environ.copy()
    merged["OPENLIA_DB_URL"] = db_url
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT_SERVER,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def test_alembic_env_loads(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/empty.db"
    result = _run_alembic(["current"], db_url)
    assert result.returncode == 0, result.stderr


def test_baseline_upgrade_creates_all_tables(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/upgrade.db"
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr

    eng = create_engine(db_url)
    inspector = inspect(eng)
    actual = set(inspector.get_table_names()) - {"alembic_version"}
    assert actual == EXPECTED_TABLES, (
        f"Missing: {EXPECTED_TABLES - actual}\nExtra: {actual - EXPECTED_TABLES}"
    )


def test_baseline_downgrade_drops_all_tables(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/downgrade.db"
    up = _run_alembic(["upgrade", "head"], db_url)
    assert up.returncode == 0, up.stderr
    down = _run_alembic(["downgrade", "base"], db_url)
    assert down.returncode == 0, down.stderr

    eng = create_engine(db_url)
    inspector = inspect(eng)
    remaining = set(inspector.get_table_names()) - {"alembic_version"}
    assert remaining == set()


def test_baseline_is_idempotent(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/twice.db"
    r1 = _run_alembic(["upgrade", "head"], db_url)
    assert r1.returncode == 0, r1.stderr
    r2 = _run_alembic(["upgrade", "head"], db_url)
    assert r2.returncode == 0, r2.stderr


def test_llm_models_has_no_tier_columns(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/no_tier.db"
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr

    eng = create_engine(db_url)
    cols = {c["name"] for c in inspect(eng).get_columns("llm_models")}
    assert "tier" not in cols
    assert "is_tier_default" not in cols


def test_llm_slot_defaults_table_exists_with_correct_shape(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/slot_defaults.db"
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr

    eng = create_engine(db_url)
    inspector = inspect(eng)
    cols = {c["name"]: c for c in inspector.get_columns("llm_slot_defaults")}
    assert set(cols.keys()) == {"slot_kind", "slot_id", "model_id", "updated_at"}
    pk = inspector.get_pk_constraint("llm_slot_defaults")
    assert set(pk["constrained_columns"]) == {"slot_kind", "slot_id"}
