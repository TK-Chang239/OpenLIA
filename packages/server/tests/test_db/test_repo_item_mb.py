from openlia_server.db.models.content import RepoItem


def test_repo_item_has_mb_v2_report_id_column():
    assert "mb_v2_report_id" in RepoItem.__table__.columns


def test_repo_item_mb_v2_report_id_is_nullable():
    assert RepoItem.__table__.columns["mb_v2_report_id"].nullable is True


def test_repo_item_check_constraint_counts_five_targets():
    checks = [
        con.sqltext.text
        for con in RepoItem.__table__.constraints
        if con.__class__.__name__ == "CheckConstraint"
    ]
    assert any("mb_v2_report_id" in c for c in checks)
