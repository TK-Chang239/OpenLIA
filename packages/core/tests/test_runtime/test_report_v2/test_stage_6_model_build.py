"""Tests for stage_6_model_build — ModelBuilder parallel dispatch with retry."""

from __future__ import annotations

from unittest.mock import MagicMock

from openlia.llm.runtime.report_v2.pipeline.stage_6_model_build import (
    ModelBuilder,
)
from openlia.llm.runtime.report_v2.schemas.plan import ArtifactSpec
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperRegistration,
    HelperSchema,
    register_helper,
    reset_helpers_for_tests,
)


def _make_dcf_helper(execute_fn=None) -> None:
    schema = HelperSchema(
        name="dcf",
        description="DCF model",
        params={
            "base_revenue": HelperParam(
                type="float",
                required=True,
                derivation="extract base_revenue from research_pool financials",
                description="Base revenue figure",
            ),
            "discount_rate": HelperParam(
                type="float",
                default=0.1,
                required=False,
                description="Discount rate",
            ),
        },
    )
    fn = execute_fn or (lambda **kw: {"npv": 100})
    register_helper(HelperRegistration(schema=schema, execute=fn, available=True))


class TestBuildSuccess:
    def setup_method(self):
        reset_helpers_for_tests()
        _make_dcf_helper()

    def test_build_success(self):
        llm = MagicMock()
        spec = ArtifactSpec(
            id="a1",
            type="table",
            description="DCF output",
            helper="dcf",
            parameters={"base_revenue": 500.0, "discount_rate": 0.08},
        )
        builder = ModelBuilder(llm=llm, max_workers=1)
        results = builder.build([spec], research_pool={})
        assert len(results) == 1
        artifact = results[0]
        assert artifact.status == "OK"
        assert artifact.content == {"npv": 100}
        assert artifact.resolved_params["base_revenue"] == 500.0


class TestUnresolvableRequiredParam:
    def setup_method(self):
        reset_helpers_for_tests()
        _make_dcf_helper()

    def test_unresolvable_required_param_marks_failed(self):
        llm = MagicMock()
        llm.call.return_value = {"value": None}
        spec = ArtifactSpec(
            id="a2",
            type="table",
            description="DCF output no params",
            helper="dcf",
            parameters={},
        )
        builder = ModelBuilder(llm=llm, max_workers=1)
        results = builder.build([spec], research_pool={})
        assert len(results) == 1
        artifact = results[0]
        assert artifact.status == "FAILED"
        assert "base_revenue" in (artifact.failure_reason or "")


class TestNoHelperAssigned:
    def setup_method(self):
        reset_helpers_for_tests()

    def test_no_helper_assigned_fails_with_reason(self):
        llm = MagicMock()
        spec = ArtifactSpec(
            id="a3",
            type="kpi_strip",
            description="Mystery artifact",
            helper=None,
        )
        builder = ModelBuilder(llm=llm, max_workers=1)
        results = builder.build([spec], research_pool={})
        assert len(results) == 1
        artifact = results[0]
        assert artifact.status == "FAILED"
        assert "no helper assigned" in (artifact.failure_reason or "").lower()


class TestUnregisteredHelper:
    def setup_method(self):
        reset_helpers_for_tests()

    def test_unregistered_helper_fails(self):
        llm = MagicMock()
        spec = ArtifactSpec(
            id="a4",
            type="table",
            description="Uses unknown helper",
            helper="nonexistent",
        )
        builder = ModelBuilder(llm=llm, max_workers=1)
        results = builder.build([spec], research_pool={})
        assert len(results) == 1
        artifact = results[0]
        assert artifact.status == "FAILED"
        assert "not registered" in (artifact.failure_reason or "").lower()


class TestDeferredHelper:
    def setup_method(self):
        reset_helpers_for_tests()

    def test_deferred_helper_fails_with_category(self):
        register_helper(
            HelperRegistration(
                schema=HelperSchema(
                    name="var_calculator",
                    description="Value at Risk",
                    params={},
                ),
                execute=lambda **kw: 1,
                available=False,
                deferred_category="risk_metrics",
            )
        )
        llm = MagicMock()
        spec = ArtifactSpec(
            id="a5",
            type="table",
            description="VaR calc",
            helper="var_calculator",
        )
        builder = ModelBuilder(llm=llm, max_workers=1)
        results = builder.build([spec], research_pool={})
        assert len(results) == 1
        artifact = results[0]
        assert artifact.status == "FAILED"
        assert "deferred category" in (artifact.failure_reason or "").lower()
        assert "risk_metrics" in (artifact.failure_reason or "")


class TestHelperExceptionRetry:
    def setup_method(self):
        reset_helpers_for_tests()

    def test_helper_exception_retries_once(self):
        calls = []

        def flaky(**kw):
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("transient")
            return {"ok": True}

        _make_dcf_helper(execute_fn=flaky)
        llm = MagicMock()
        spec = ArtifactSpec(
            id="a6",
            type="table",
            description="Flaky DCF",
            helper="dcf",
            parameters={"base_revenue": 300.0},
        )
        builder = ModelBuilder(llm=llm, max_workers=1)
        results = builder.build([spec], research_pool={})
        assert len(results) == 1
        artifact = results[0]
        assert artifact.status == "OK"
        assert artifact.content == {"ok": True}
        assert len(calls) == 2
