"""Repo cloning for connector grounding (Phase A step 2).

Connectors with `source_repo_url` get shallow-cloned to a per-connector
local directory. The agentic resolver's filesystem tools then operate
against that clone. These tests use real `git` against local file://
repos -- no network, no mocks of git itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from openlia_server.services.grounding_clone import (
    GroundingCloneError,
    clone_repo,
    delete_clone,
)


def _init_local_repo(repo_path: Path, branch: str = "main") -> str:
    """Create a single-commit git repo. Return the HEAD commit SHA."""
    repo_path.mkdir(parents=True, exist_ok=True)
    env_args = [
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test",
        "-c",
        "init.defaultBranch=" + branch,
    ]
    subprocess.run(
        ["git", *env_args, "init", "-b", branch, str(repo_path)],
        check=True,
        capture_output=True,
    )
    (repo_path / "README.md").write_text("hello\n")
    subprocess.run(
        ["git", "-C", str(repo_path), *env_args, "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), *env_args, "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    out = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def test_clone_repo_returns_sha_and_creates_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    expected_sha = _init_local_repo(src)
    target = tmp_path / "clone"

    sha = clone_repo(url=f"file://{src}", target=target, revision="main")

    assert sha == expected_sha
    assert (target / "README.md").read_text() == "hello\n"


def test_clone_repo_rejects_unsupported_scheme(tmp_path: Path) -> None:
    target = tmp_path / "clone"

    with pytest.raises(GroundingCloneError):
        clone_repo(url="git@github.com:foo/bar.git", target=target, revision="main")


def test_clone_repo_rejects_private_ip(tmp_path: Path) -> None:
    target = tmp_path / "clone"

    with pytest.raises(GroundingCloneError):
        clone_repo(
            url="https://192.168.0.1/repo.git",
            target=target,
            revision="main",
        )


def test_clone_repo_rejects_localhost(tmp_path: Path) -> None:
    target = tmp_path / "clone"

    with pytest.raises(GroundingCloneError):
        clone_repo(
            url="https://localhost/repo.git",
            target=target,
            revision="main",
        )


def test_clone_repo_rejects_plain_http(tmp_path: Path) -> None:
    target = tmp_path / "clone"

    with pytest.raises(GroundingCloneError):
        clone_repo(
            url="http://github.com/foo/bar.git",
            target=target,
            revision="main",
        )


def test_clone_repo_raises_on_invalid_url(tmp_path: Path) -> None:
    target = tmp_path / "clone"

    with pytest.raises(GroundingCloneError):
        clone_repo(
            url=f"file://{tmp_path}/does-not-exist",
            target=target,
            revision="main",
        )


def test_clone_repo_raises_on_existing_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _init_local_repo(src)
    target = tmp_path / "clone"
    target.mkdir()  # pre-existing, non-empty acts the same as empty here

    with pytest.raises(GroundingCloneError):
        clone_repo(url=f"file://{src}", target=target, revision="main")


def test_delete_clone_removes_directory(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _init_local_repo(src)
    target = tmp_path / "clone"
    clone_repo(url=f"file://{src}", target=target, revision="main")
    assert target.is_dir()

    delete_clone(target)

    assert not target.exists()


def test_delete_clone_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "never-existed"

    delete_clone(target)  # must not raise


def test_clone_repo_is_shallow(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _init_local_repo(src)
    # Add a second commit so a non-shallow clone would have depth=2.
    (src / "more.md").write_text("more\n")
    subprocess.run(
        [
            "git",
            "-C",
            str(src),
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "add",
            ".",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(src),
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "commit",
            "-m",
            "second",
        ],
        check=True,
        capture_output=True,
    )

    # Use file:// URL: git ignores `--depth` for plain local paths
    # (it uses hardlinks). file:// makes git treat it like a remote
    # repo, exercising the same code path production HTTPS URLs hit.
    target = tmp_path / "clone"
    clone_repo(url=f"file://{src}", target=target, revision="main")

    log = subprocess.run(
        ["git", "-C", str(target), "rev-list", "--count", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert log == "1", f"expected shallow (1 commit), got {log}"
