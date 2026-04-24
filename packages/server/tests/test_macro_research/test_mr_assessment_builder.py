from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from openlia.llm.runtime.messages import BatchResult, ReportRequest
from openlia_server.services.mr_assessment import MRAssessmentBuilderImpl


@pytest.fixture
def builder() -> MRAssessmentBuilderImpl:
    provider = MagicMock()
    provider.fetch.return_value = {"price": 100.0}
    return MRAssessmentBuilderImpl(data_provider=provider)


def test_builds_batch_items_for_t4_dashboards(builder: MRAssessmentBuilderImpl) -> None:
    session = MagicMock()
    payload = builder.build(session=session, user_id="u-1")
    assert len(payload.items) >= 2
    slugs = {item.id for item in payload.items}
    assert "world_order" in slugs
    assert "five_forces" in slugs


def test_synthesize_produces_report_request(builder: MRAssessmentBuilderImpl) -> None:
    session = MagicMock()
    payload = builder.build(session=session, user_id="u-1")
    t4_results = [
        BatchResult(
            id="world_order",
            ok=True,
            data={"stage": "Pressure", "severity": "amber"},
            error=None,
        ),
        BatchResult(
            id="five_forces",
            ok=True,
            data={"scores": [6, 7, 5, 4, 3]},
            error=None,
        ),
    ]
    req = payload.synthesize(t4_results)
    assert isinstance(req, ReportRequest)
    assert req.mode == "synthesis"
    assert req.length in ("brief", "standard", "long")


def test_input_hash_stable() -> None:
    h1 = MRAssessmentBuilderImpl.input_hash({"a": 1, "b": 2})
    h2 = MRAssessmentBuilderImpl.input_hash({"b": 2, "a": 1})
    assert h1 == h2
