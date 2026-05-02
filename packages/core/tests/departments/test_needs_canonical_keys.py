"""Phase 2: per-need ``canonical_keys`` annotation tests.

Every ``list[dict]``-shaped need must declare a ``canonical_keys`` map so
the resolver LLM and the runtime executor know which keys the dept-side
adapter expects. Scalar needs must NOT declare it.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from openlia.departments.loader import _needs_path, load_needs


def test_loader_parses_canonical_keys_for_list_dict_shapes() -> None:
    mr_needs = {n.id: n for n in load_needs("macro_research")}
    rs_needs = {n.id: n for n in load_needs("retail_sentiment")}

    geo = mr_needs["geopolitical_news"]
    assert geo.shape == "list[dict]"
    assert geo.canonical_keys is not None
    assert set(geo.canonical_keys.keys()) >= {"title", "url", "published_at"}

    posts = rs_needs["social_posts"]
    assert posts.shape == "list[dict]"
    assert posts.canonical_keys is not None
    assert set(posts.canonical_keys.keys()) >= {
        "id",
        "ticker",
        "source",
        "text",
        "created_at",
    }

    # Scalar needs have no canonical_keys.
    debt_gdp = mr_needs["debt_gdp"]
    assert debt_gdp.shape == "float"
    assert debt_gdp.canonical_keys is None


def test_loader_rejects_canonical_keys_on_scalar_shape(tmp_path: Path) -> None:
    bad = tmp_path / "macro_research.needs.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            department: macro_research
            needs:
              - id: bogus_scalar
                description: invalid
                parameters: []
                shape: float
                canonical_keys:
                  ticker: str
            """
        ).strip(),
        encoding="utf-8",
    )
    # Re-route the loader to the temp dir for one call.
    real_path = _needs_path("macro_research")
    try:
        # Symlink-replace via a custom override: simplest is monkey-call via
        # writing the same path. Instead, we test the validator directly by
        # invoking the loader's parser on a temp path through monkeypatch.
        import openlia.departments.loader as L

        original = L._needs_path
        L._needs_path = lambda dept_id: bad if dept_id == "macro_research" else original(dept_id)
        with pytest.raises(ValueError, match="canonical_keys"):
            load_needs("macro_research")
    finally:
        L._needs_path = original  # type: ignore[name-defined]
        assert _needs_path("macro_research") == real_path


def test_loader_rejects_list_dict_shape_without_canonical_keys(tmp_path: Path) -> None:
    bad = tmp_path / "retail_sentiment.needs.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            department: retail_sentiment
            needs:
              - id: social_posts
                description: missing canonical_keys
                parameters:
                  - name: ticker
                    description: t
                    type: str
                    required: true
                shape: list[dict]
            """
        ).strip(),
        encoding="utf-8",
    )

    import openlia.departments.loader as L

    original = L._needs_path
    L._needs_path = lambda dept_id: bad if dept_id == "retail_sentiment" else original(dept_id)
    try:
        with pytest.raises(ValueError, match="canonical_keys"):
            load_needs("retail_sentiment")
    finally:
        L._needs_path = original


def test_canonical_key_values_are_strings() -> None:
    """Canonical key map values are type-hint strings (e.g. 'str', 'int', 'dict')."""
    rs_needs = {n.id: n for n in load_needs("retail_sentiment")}
    posts = rs_needs["social_posts"]
    for key, type_hint in posts.canonical_keys.items():
        assert isinstance(key, str) and key
        assert isinstance(type_hint, str) and type_hint
