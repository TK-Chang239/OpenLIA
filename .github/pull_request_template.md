<!--
For equity research v2.2 helper PRs (Phases 0-4 per impl plan), all
sections below are required. For non-helper PRs, delete the
"Equity research helper" block and keep "General".
-->

## Summary

<!-- 1-3 bullet points: what this PR does and why -->

## General

- [ ] Linked issue or task # (if applicable):
- [ ] Tests added or updated
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest` passes

---

## Equity research helper PR (delete if not applicable)

### Plan binding

- **Impl plan PR row:** <!-- e.g. PR 2.2 — DCF engine + cost of capital -->
- **Design-doc sections implemented** (must match impl plan §14):
  <!-- e.g. helpers-design §5, §5.2-5.5; schema-and-skills §3; artifact-injection §5 -->

### Audit fixes applied

<!--
List every audit fix from the impl plan row for this PR. Check off
each one. If a fix doesn't apply, explain why. Empty list means PR
is incomplete unless the row genuinely has no audit fixes.
-->

- [ ]
- [ ]

### Cross-cutting requirements (impl plan §8)

- [ ] Helper(s) use the four-tier sub-model schema; no legacy `description`-only entry
- [ ] New ArtifactType entries land in `artifact_types.yaml` with their Pydantic model
- [ ] `section_plan_defaults.yaml` updated for any artifact appearing in `stock_initiation_v2` (or the sector template, for Phase 3)
- [ ] At minimum one happy-path test + one failure case per new helper
- [ ] `skills/<helper>.md` authored if helper appears in schema-and-skills §6 list
- [ ] `purpose` / `when_to_use` / `when_not_to_use` populated; no `description`-field fallback

### Stage 6 contract

- [ ] `produces_artifacts` and `consumes_artifacts` accurately reflect what the helper returns and needs
- [ ] `data_dependencies` lists every external data source the helper touches
- [ ] Helper return type is a typed Pydantic model (`RenderableArtifact` subclass) registered via `return_type=`
- [ ] DAG validation passes at registry boot

### Stage 7a contract

- [ ] Each new artifact implements `to_markdown(level)` at HEADLINE / SUMMARY / FULL
- [ ] HEADLINE contains at least one quantitative anchor (verifier rejects otherwise)
- [ ] No fidelity level overflows its hard cap (HEADLINE 120 / SUMMARY 600 / FULL 3000 tokens)

### Determinism

- [ ] Helper produces byte-identical output for identical inputs (modulo external data fetches, which are recorded as fixtures in tests)
- [ ] No module-level mutable state
- [ ] No side effects outside the Connector layer

---

## Test plan

<!-- Bulleted markdown checklist for what was tested -->

- [ ]
