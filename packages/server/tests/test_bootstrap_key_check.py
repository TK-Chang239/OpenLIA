"""Bootstrap fails loudly in company mode when no encryption key is configured."""
from __future__ import annotations

import pytest

from openlia_server.db import secrets_crypto as sc


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_company_mode_bootstrap_requires_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path / 'b.db'}")
    from openlia_server.db.bootstrap import bootstrap

    with pytest.raises(sc.SecretKeyMissingError):
        bootstrap()


def test_personal_mode_bootstrap_provisions_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path / 'b.db'}")
    from openlia_server.db.bootstrap import bootstrap

    bootstrap()  # should not raise; provisions ~OPENLIA_HOME/secret.key
    assert (tmp_path / sc.KEY_FILENAME).exists()
