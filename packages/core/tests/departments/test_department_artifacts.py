"""Drift-safety tests for per-department artifacts (spec §5.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia.departments import get_registered_department_ids
from openlia.departments.loader import (
    all_departments,
    load_needs,
    load_routing_context,
)
from openlia.macro_research.dashboards import DASHBOARDS

_DEPT_DIR = Path(__file__).resolve().parents[2] / "src" / "openlia" / "departments"

_REQUIRED_H2_SECTIONS = (
    "## What this department does",
    "## Data this department needs access to",
    "## Out-of-scope topics",
    "## Example prompts and the data they imply",
)

# Approximate token-count floor: ~300 tokens ≈ ~225 words at the
# usual GPT/Claude tokenizer ratio. We use words rather than chars
# to stay tokenizer-agnostic.
_MIN_WORDS = 225


def _all_dept_ids() -> list[str]:
    return get_registered_department_ids()


def _t1_requirement_to_need_id(raw: str) -> str:
    """Extract the need id from a legacy `kind:value` T1 requirement.

    The dashboards historically prefix each requirement with a kind
    (`macro_indicator:debt_gdp`, `stock_quote:TIP`,
    `company_news:geopolitical`). The corresponding need id in
    needs.yaml is:
      - `<value>` for `macro_indicator:<value>`
      - `stock_quote` for any `stock_quote:<ticker>` (one parameterized
        need covers all tickers)
      - `<value>_news` for `company_news:<value>` (e.g. geopolitical
        → geopolitical_news)
    Anything else passes through unchanged so a future dashboard with
    a bare need id (the spec's `T1_NEEDS` form) just works.
    """
    if ":" not in raw:
        return raw
    kind, _, value = raw.partition(":")
    if kind == "macro_indicator":
        return value
    if kind == "stock_quote":
        return "stock_quote"
    if kind == "company_news":
        return f"{value}_news"
    return raw


def _runner_need_ids_for(department_id: str) -> set[str]:
    """Walk runner code for `department_id` and return referenced need ids.

    Today only Macro Research has runner code we statically introspect.
    For Retail Sentiment the spec hard-codes `social_posts` (§9.5);
    that reference is captured here directly so the drift-safety check
    still triggers if the YAML drifts.
    """
    if department_id == "macro_research":
        ids: set[str] = set()
        for dashboard in DASHBOARDS.values():
            for raw in getattr(dashboard, "T1_REQUIREMENTS", ()) or ():
                ids.add(_t1_requirement_to_need_id(raw))
            # Forward-compat: support the spec's `T1_NEEDS` shape too.
            for need_id in getattr(dashboard, "T1_NEEDS", ()) or ():
                ids.add(str(need_id))
        return ids
    if department_id == "retail_sentiment":
        return {"social_posts"}
    return set()


@pytest.mark.parametrize("department_id", _all_dept_ids())
def test_routing_context_exists_and_has_required_sections(department_id: str) -> None:
    text = load_routing_context(department_id)
    word_count = len(text.split())
    assert word_count >= _MIN_WORDS, (
        f"{department_id}.routing_context.md has {word_count} words; "
        f"need at least {_MIN_WORDS} (~300 tokens)."
    )
    for header in _REQUIRED_H2_SECTIONS:
        assert header in text, (
            f"{department_id}.routing_context.md missing required H2 section: {header!r}"
        )


@pytest.mark.parametrize("department_id", _all_dept_ids())
def test_needs_yaml_present_when_runner_required(department_id: str) -> None:
    dept = next(d for d in all_departments() if getattr(d, "name", None) == department_id)
    requires_runner = bool(getattr(dept, "requires_runner", False))
    needs = load_needs(department_id)
    if requires_runner:
        path = _DEPT_DIR / f"{department_id}.needs.yaml"
        assert path.exists(), f"{department_id}: requires_runner=True but {path.name} is missing."
        assert needs, f"{department_id}: needs.yaml must declare at least one need."
        # Each need must have a non-empty id and description.
        for need in needs:
            assert need.id.strip(), f"{department_id}: a need has an empty id."
            assert need.description.strip(), (
                f"{department_id}: need '{need.id}' has an empty description."
            )
    elif department_id in ("macro_research", "retail_sentiment"):
        # Dashboard depts (requires_runner=False) that retain their need
        # declarations as connector-resolution metadata. The builtin connector
        # templates' runner_specs reference these need ids, so the files must
        # not be deleted even though the depts are no longer runtime-runner gated.
        path = _DEPT_DIR / f"{department_id}.needs.yaml"
        assert path.exists(), f"{department_id}: expected retained needs.yaml is missing."
        assert needs, f"{department_id}: needs.yaml must declare at least one need."
    else:
        # Chat-flow depts: no needs.yaml is the expected state.
        path = _DEPT_DIR / f"{department_id}.needs.yaml"
        assert not path.exists(), (
            f"{department_id}: requires_runner=False but a needs.yaml is present."
        )


@pytest.mark.parametrize("department_id", _all_dept_ids())
def test_runner_referenced_ids_are_declared(department_id: str) -> None:
    referenced = _runner_need_ids_for(department_id)
    if not referenced:
        return
    declared = {n.id for n in load_needs(department_id)}
    missing = referenced - declared
    assert not missing, (
        f"{department_id}: runner code references need ids not declared in "
        f"needs.yaml: {sorted(missing)}"
    )


@pytest.mark.parametrize("department_id", _all_dept_ids())
def test_declared_ids_are_referenced_by_runner(department_id: str) -> None:
    declared = {n.id for n in load_needs(department_id)}
    if not declared:
        return
    referenced = _runner_need_ids_for(department_id)
    unused = declared - referenced
    assert not unused, (
        f"{department_id}: needs.yaml declares ids unreferenced by runner code: {sorted(unused)}"
    )


def test_load_routing_context_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_routing_context("not_a_real_department")


def test_load_needs_missing_returns_empty_list() -> None:
    # An unregistered dept's missing needs.yaml is the chat-flow case.
    assert load_needs("not_a_real_department") == []
