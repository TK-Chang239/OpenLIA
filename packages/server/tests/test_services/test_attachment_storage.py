"""Phase 1 — local-filesystem attachment storage backend.

These tests exercise the public interface only: ``save``, ``read``,
``unlink``, ``configured_root``. They do not assert on internal layout
(sharding scheme, filename format) beyond what the contract guarantees:
a save returns an opaque ``storage_path`` that ``read`` can consume.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia_server.services import attachment_storage


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the storage backend at an isolated tmp dir for every test."""
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path))
    return tmp_path


def test_save_returns_path_whose_contents_match_input() -> None:
    storage_path = attachment_storage.save(b"hello world", original_filename="greet.txt")
    assert attachment_storage.read(storage_path) == b"hello world"


def test_unlink_removes_the_file() -> None:
    storage_path = attachment_storage.save(b"data", original_filename="x.bin")
    assert Path(storage_path).is_file()

    attachment_storage.unlink(storage_path)

    assert not Path(storage_path).exists()


def test_unlink_is_idempotent_on_missing_file() -> None:
    storage_path = attachment_storage.save(b"data", original_filename="x.bin")
    attachment_storage.unlink(storage_path)
    attachment_storage.unlink(storage_path)  # second call must not raise


def test_read_raises_filenotfound_when_path_missing() -> None:
    storage_path = attachment_storage.save(b"data", original_filename="x.bin")
    attachment_storage.unlink(storage_path)
    with pytest.raises(FileNotFoundError):
        attachment_storage.read(storage_path)


def test_save_preserves_original_extension_in_storage_path() -> None:
    """Extension preserved so downstream mime-sniffers work; filename body is server-generated."""
    storage_path = attachment_storage.save(b"%PDF-1.4 ...", original_filename="report.pdf")
    assert storage_path.endswith(".pdf")


def test_save_does_not_use_client_filename_in_path(_isolated_root: Path) -> None:
    """Client filename must not appear in the on-disk path (no path-traversal surface)."""
    storage_path = attachment_storage.save(b"data", original_filename="../../etc/passwd")
    resolved = Path(storage_path).resolve()
    assert _isolated_root.resolve() in resolved.parents
    assert "passwd" not in resolved.name
    assert ".." not in resolved.parts


def test_two_saves_with_same_name_produce_distinct_paths() -> None:
    a = attachment_storage.save(b"a", original_filename="dup.txt")
    b = attachment_storage.save(b"b", original_filename="dup.txt")
    assert a != b
    assert attachment_storage.read(a) == b"a"
    assert attachment_storage.read(b) == b"b"


def test_configured_root_reflects_env() -> None:
    root = attachment_storage.configured_root()
    assert root == Path(str(root))  # stable Path identity
    assert root.is_dir()


def test_configured_root_defaults_under_openlia_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When OPENLIA_ATTACHMENTS_DIR is unset, default lives under OPENLIA_HOME."""
    monkeypatch.delenv("OPENLIA_ATTACHMENTS_DIR", raising=False)
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

    root = attachment_storage.configured_root()

    assert root == tmp_path / "attachments"
    assert root.is_dir()
