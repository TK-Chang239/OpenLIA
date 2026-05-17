"""When a report is hard-deleted by the retention sweep, its bundle
file is also deleted from disk."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from openlia_server.services.scheduler import sweep_expired_reports


@pytest.fixture
def seeded_expired_report_with_bundle(db_session_factory, tmp_path: Path):
    from openlia_server.db.models.content import Report

    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()

    report_id = "rpt-expired-bundle-001"
    now = datetime.now(UTC)

    with db_session_factory() as session:
        row = Report(
            id=report_id,
            user_id=None,
            department="equity_research",
            report_type="stock_initiation",
            title="Expired Report",
            subject="AAPL",
            content_markdown="# Body",
            content_structured={"cover": {"title": "Expired Report"}},
            model_ref="test-model",
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        )
        session.add(row)
        session.commit()

    bundle_path = bundle_dir / f"{report_id}.json.gz"
    bundle_path.write_bytes(b"fake-bundle-data")

    class _Fixture:
        id = report_id

    return _Fixture()


def test_bundle_file_removed_when_report_hard_deleted(
    db_session_factory, tmp_path: Path, seeded_expired_report_with_bundle
) -> None:
    report_id = seeded_expired_report_with_bundle.id
    bundle_path = tmp_path / "bundles" / f"{report_id}.json.gz"
    assert bundle_path.exists()  # fixture writes it
    with db_session_factory() as session:
        sweep_expired_reports(session=session, bundle_dir=tmp_path / "bundles")
    assert not bundle_path.exists(), "bundle file must be removed when report is hard-deleted"
