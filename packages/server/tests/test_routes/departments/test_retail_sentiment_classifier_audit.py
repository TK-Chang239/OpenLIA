"""HTTP-path tests for RsRunner audit-log wiring.

POST /departments/retail_sentiment/run drives RsRunner end-to-end; a
classifier that emits audits must cause one `rs_classification_log` row
per audit to land in the DB. The NeutralClassifier default case writes
no log rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from openlia.retail_sentiment.schemas import (
    BatchClassifyResult,
    ClassificationAudit,
    ClassificationLabel,
    ClassifiedItem,
    RawSocialPost,
)
from openlia_server.db.models.dashboard import RsClassificationLog
from openlia_server.services.rs_runner import RsRunner


class _AuditingClassifier:
    def __init__(self, *, audits: list[ClassificationAudit]) -> None:
        self._audits = audits

    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        items = [
            ClassifiedItem(
                id=p.id,
                classification=ClassificationLabel.BULLISH,
                confidence=0.8,
                key_phrases=["ok"],
            )
            for p in posts
        ]
        return BatchClassifyResult(items=items, audits=list(self._audits))


@pytest.fixture
def rs_runner_with_classifier(company_client, auth_user):
    from openlia_server.db import session as session_mod

    def _build(*, classifier) -> None:
        company_client.app.state.rs_runner = RsRunner(
            session_factory=session_mod.SessionLocal,
            classifier=classifier,
        )

    return _build


def test_run_default_classifier_writes_no_audit_rows(company_client, auth_user, db_session) -> None:
    from openlia_server.db import session as session_mod

    company_client.app.state.rs_runner = RsRunner(
        session_factory=session_mod.SessionLocal,
    )

    r = company_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    assert r.status_code == 200

    assert db_session.query(RsClassificationLog).count() == 0


def test_run_with_audits_persists_classification_log_row(
    rs_runner_with_classifier, company_client, db_session
) -> None:
    audit = ClassificationAudit(
        batch_id="b-1",
        ticker="AAPL",
        model_ref="gpt-5.4",
        item_count=5,
        prompt_tokens=12,
        completion_tokens=24,
        latency_ms=150,
        error=None,
    )
    rs_runner_with_classifier(classifier=_AuditingClassifier(audits=[audit]))

    r = company_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    assert r.status_code == 200

    rows = db_session.query(RsClassificationLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.batch_id == "b-1"
    assert row.ticker == "AAPL"
    assert row.model_ref == "gpt-5.4"
    assert row.item_count == 5
    assert row.prompt_tokens == 12
    assert row.completion_tokens == 24
    assert row.latency_ms == 150
    assert row.error is None


def test_run_audit_error_persists(rs_runner_with_classifier, company_client, db_session) -> None:
    audit = ClassificationAudit(
        batch_id="b-err",
        ticker="AAPL",
        model_ref="gpt-5.4",
        item_count=5,
        latency_ms=75,
        error="ValueError: expected 5 items, got 1",
    )
    rs_runner_with_classifier(classifier=_AuditingClassifier(audits=[audit]))

    r = company_client.post("/departments/retail_sentiment/run", json={"tickers": ["AAPL"]})
    assert r.status_code == 200

    row = db_session.query(RsClassificationLog).one()
    assert row.error == "ValueError: expected 5 items, got 1"
    assert row.prompt_tokens == 0
    assert row.completion_tokens == 0
