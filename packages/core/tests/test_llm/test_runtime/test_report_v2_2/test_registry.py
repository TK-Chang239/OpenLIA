"""Helper registry tests."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.enums import Category
from openlia.llm.runtime.report_v2_2.schema import (
    DirectoryEntry,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import (
    get_helper,
    list_helpers,
    register_helper,
    reset_helpers_for_tests,
)


def _make_schema(name: str, artifact: str = "dcf_valuation_output") -> HelperSchema:
    return HelperSchema(
        directory=DirectoryEntry(name=name, category=Category.DCF, one_liner="Test helper."),
        selection=SelectionGuidance(
            purpose="Test.",
            when_to_use=["When testing"],
            when_not_to_use=["In production"],
        ),
        contract=MechanicalContract(
            params={},
            outputs=[],
            produces_artifacts=[artifact],
            consumes_artifacts=[],
        ),
    )


def _noop(**kwargs: object) -> dict:  # type: ignore[type-arg]
    return {}


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_helpers_for_tests()
    yield  # type: ignore[misc]
    reset_helpers_for_tests()


def test_register_and_list() -> None:
    schema = _make_schema("my_helper")
    register_helper(schema, _noop)
    helpers = list_helpers()
    assert len(helpers) == 1
    assert helpers[0].schema.directory.name == "my_helper"


def test_get_helper_returns_registered() -> None:
    schema = _make_schema("my_helper")
    register_helper(schema, _noop)
    h = get_helper("my_helper")
    assert h is not None
    assert h.schema.directory.name == "my_helper"


def test_get_helper_returns_none_for_unknown() -> None:
    assert get_helper("nonexistent") is None


def test_duplicate_registration_raises() -> None:
    schema = _make_schema("dup_helper")
    register_helper(schema, _noop)
    with pytest.raises(ValueError, match="already registered"):
        register_helper(schema, _noop)


def test_unknown_artifact_type_raises() -> None:
    schema = _make_schema("bad_helper", artifact="nonexistent_artifact_xyz")
    with pytest.raises(ValueError, match="nonexistent_artifact_xyz"):
        register_helper(schema, _noop)


def test_register_multiple_helpers() -> None:
    for i in range(3):
        schema = _make_schema(f"helper_{i}")
        register_helper(schema, _noop)
    assert len(list_helpers()) == 3


def test_impl_is_callable() -> None:
    schema = _make_schema("callable_helper")
    register_helper(schema, _noop)
    h = get_helper("callable_helper")
    assert h is not None
    assert callable(h.impl)
    result = h.impl()
    assert isinstance(result, dict)
