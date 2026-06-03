# Remove the legacy Macro Research tiered-engine layer

**Goal:** Delete the dead tiered (T1-T5) Macro Research engine — superseded by the live `report_dash_mr` LLM tool-use engine (`MR_DASH` job, `MrDashboardCache`). The legacy layer is confirmed inert: nothing enqueues `MR_ASSESSMENT`, and `app.state.mr_runner`/`mr_cache_store` are set but never read.

**Out of scope (separate efforts):**
- `macro_research.needs.yaml` + `requires_runner=True` — shared health machinery (Retail Sentiment also uses it); flipping it changes dept-health behavior and belongs with the connector-requirement relaxation (spec §9).
- `dalio_copy/*.ts` fallbacks (kept as test fixtures).

## What is legacy (remove) vs live (keep)

| Legacy (remove) | Live (keep) |
| --- | --- |
| `macro_research/assembler.py` (`DashboardAssembler`) | `report_dash_mr/` engine |
| `services/mr_runner.py` (`MRRunner`) | `services/mr_dash_run_service.py` |
| `services/mr_assessment.py` (`MRAssessmentBuilderImpl`) | `services/mr_dashboard.py` (`MRDashboardService`, `MrDashboardState`) |
| `services/mr_cache.py` (`MRCacheStoreImpl`) | `services/mr_schedules.py` (`MRScheduleService`, `MR_DASH`) |
| `scheduler/executors/mr.py` (`MRAssessmentExecutor`) | `scheduler/executors/mr_dash.py` (`MrDashExecutor`) |
| `JobType.MR_ASSESSMENT` | `JobType.MR_DASH` |
| `db.models.dashboard.MrAssessmentCache` (`mr_assessment_cache` table) | `MrDashboardCache`, `MrDashboardState` |
| scheduler `mr_builder` / `mr_cache_store` / `batch_runner` wiring params | — |
| `app.py` `mr_runner` / `mr_cache_store` / `mr_data_provider` / `_MRDataFetchAdapter` | `app.py` `mr_dashboard_svc` / `mr_schedule_svc` / snapshot reader |

## Removal order (leaf → root → tests)

1. **Leaf modules + their tests** — delete `assembler.py`, `mr_runner.py`, `mr_assessment.py`, `mr_cache.py`; delete `test_assembler.py`, `test_mr_runner.py`, `test_mr_assessment_builder.py`, `test_mr_cache_store.py`; drop the `DashboardAssembler` usage in `test_deterministic.py`.
2. **Scheduler core** — delete `executors/mr.py`; remove `MRAssessmentPayload`/`MRAssessmentBuilder`/`MRCacheStore` from `payloads.py`; remove `JobType.MR_ASSESSMENT` + its `_DEPARTMENT_BY_JOB` entry from `registry.py`; remove the `MR_ASSESSMENT` executor entry + `mr_builder`/`mr_cache_store`/`batch_runner` params + imports from `wiring.py`; remove `wire_mr` + the `_mr_cache_store` injection from `service.py`.
3. **app wiring** — lifespan: drop `MRAssessmentBuilderImpl`/`MRCacheStoreImpl` imports, `mr_builder`/`mr_cache_store_lifespan`, `batch_runner=build_batch_runner(_sm)` arg; factory: drop `mr_cache.py`/`mr_runner.py` imports, `mr_data_provider`/`_MRDataFetchAdapter`/`MRRunner` construction, `app.state.mr_runner`/`app.state.mr_cache_store`. Keep `mr_dashboard_svc`, `mr_schedule_svc`, snapshot reader, `_NoopPtDispatcher` (used by `pt_dispatcher`).
4. **DB model + migration** — delete `MrAssessmentCache`; add Alembic revision `drop_mr_assessment_cache` (down_revision `mr_dashboard_cache`) dropping the table; fix the model docstrings.
5. **Maintenance + cli** — drop `MrAssessmentCache` cleanup + `mr_cache_deleted` from `executors/maintenance.py`; drop the `mr_assessment_cache:` line from `cli.py`.
6. **Test sweep** — remove `FakeMRCacheStore` from `_scheduler_fakes.py` / `_macro_research_fakes.py`; drop `mr_cache_store=`/`mr_builder=`/`batch_runner=` from every `build_scheduler_service` call site; delete `test_mr_executor.py`; update `test_wiring`, `test_registry`, `test_payloads`, `test_maintenance_executor`, `test_models_dashboard`, `test_migrations`, `test_dept_health_api`, `test_scheduler_service`, `test_recovery`, `test_jobs_service`, `test_app_lifespan` (swap `MR_ASSESSMENT` sentinels → `MR_DASH`).

## Verify

- `uv run ruff check . && uv run ruff format --check .`
- `uv run pytest packages/core/tests/`
- `uv run pytest packages/server/tests/test_scheduler/ packages/server/tests/test_macro_research/ packages/server/tests/test_db/` (full server suite hangs on SSE — run targeted dirs)
- `uv run pytest packages/server/tests/test_app_lifespan.py packages/server/tests/test_dept_health_api.py`
