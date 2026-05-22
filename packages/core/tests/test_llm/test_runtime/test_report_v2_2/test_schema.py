"""HelperSchema + sub-model validation tests."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.enums import Category, VerifierIssueType
from openlia.llm.runtime.report_v2_2.schema import (
    DirectoryEntry,
    HelperExample,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
)
from pydantic import ValidationError


def _make_full_schema() -> HelperSchema:
    return HelperSchema(
        version="1.0",
        deprecated_at_version=None,
        directory=DirectoryEntry(
            name="test_helper",
            category=Category.DCF,
            one_liner="Runs a test DCF valuation.",
        ),
        selection=SelectionGuidance(
            purpose="Validates the schema sub-model structure.",
            when_to_use=["Use in tests", "Use when validating schema contracts"],
            when_not_to_use=["Do not use in production", "Do not use for sector-specific work"],
        ),
        contract=MechanicalContract(
            params={
                "base_revenue": HelperParam(
                    type="list[float]",
                    description="Historical revenue series.",
                    required=True,
                ),
            },
            outputs=[
                HelperOutput(
                    name="dcf_result",
                    type="structured_object",
                    description="DCF valuation output.",
                )
            ],
            example=HelperExample(
                call={"base_revenue": [100.0, 110.0, 121.0]},
                result_shape="DCFValuationOutput",
                notes="Simple three-year history.",
            ),
            produces_artifacts=["dcf_valuation_output"],
            consumes_artifacts=[],
            data_dependencies=["eodhd.fundamentals"],
        ),
        skill_doc=SkillDocRef(path="skills/dcf_engine.md", estimated_tokens=2000),
        verifier_hooks=[VerifierIssueType.BLOCK_SHAPE],
    )


def test_full_schema_instantiates() -> None:
    schema = _make_full_schema()
    assert schema.directory.name == "test_helper"
    assert schema.directory.category == Category.DCF
    assert schema.version == "1.0"
    assert schema.deprecated_at_version is None
    assert schema.skill_doc is not None
    assert schema.skill_doc.estimated_tokens == 2000


def test_schema_missing_directory_raises() -> None:
    with pytest.raises(ValidationError):
        HelperSchema(
            selection=SelectionGuidance(
                purpose="x",
                when_to_use=["x"],
                when_not_to_use=["x"],
            ),
            contract=MechanicalContract(
                params={},
                outputs=[],
                produces_artifacts=[],
                consumes_artifacts=[],
            ),
        )  # type: ignore[call-arg]


def test_schema_missing_selection_raises() -> None:
    with pytest.raises(ValidationError):
        HelperSchema(
            directory=DirectoryEntry(name="x", category=Category.DCF, one_liner="x"),
            contract=MechanicalContract(
                params={},
                outputs=[],
                produces_artifacts=[],
                consumes_artifacts=[],
            ),
        )  # type: ignore[call-arg]


def test_schema_missing_contract_raises() -> None:
    with pytest.raises(ValidationError):
        HelperSchema(
            directory=DirectoryEntry(name="x", category=Category.DCF, one_liner="x"),
            selection=SelectionGuidance(purpose="x", when_to_use=["x"], when_not_to_use=["x"]),
        )  # type: ignore[call-arg]


def test_deprecated_at_version_accepts_none() -> None:
    schema = _make_full_schema()
    schema2 = schema.model_copy(update={"deprecated_at_version": None})
    assert schema2.deprecated_at_version is None


def test_deprecated_at_version_accepts_semver_string() -> None:
    schema = _make_full_schema()
    schema2 = schema.model_copy(update={"deprecated_at_version": "2.0"})
    assert schema2.deprecated_at_version == "2.0"


def test_skill_doc_none_for_simple_helper() -> None:
    schema = _make_full_schema()
    schema2 = schema.model_copy(update={"skill_doc": None})
    assert schema2.skill_doc is None


def test_verifier_hooks_defaults_to_empty() -> None:
    schema = HelperSchema(
        directory=DirectoryEntry(name="x", category=Category.ADAPTER, one_liner="x"),
        selection=SelectionGuidance(purpose="x", when_to_use=["x"], when_not_to_use=["x"]),
        contract=MechanicalContract(
            params={}, outputs=[], produces_artifacts=[], consumes_artifacts=[]
        ),
    )
    assert schema.verifier_hooks == []


def test_mechanical_contract_data_dependencies_defaults_to_empty() -> None:
    contract = MechanicalContract(
        params={}, outputs=[], produces_artifacts=[], consumes_artifacts=[]
    )
    assert contract.data_dependencies == []


def test_helper_param_required_default_is_true() -> None:
    param = HelperParam(type="float", description="A param.")
    assert param.required is True


def test_helper_param_default_can_be_none() -> None:
    param = HelperParam(type="float", description="A param.", default=None, required=False)
    assert param.default is None
