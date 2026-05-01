"""Resolver filesystem tools the agentic adapter LLM uses to navigate
locally-cloned connector repos.

These tools are sandboxed to a `connector_root` set by the orchestrator;
the LLM supplies relative paths but never controls the root itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia_server.services.resolver_tools import (
    ResolverToolError,
    list_directory,
    read_file,
    search_files,
)


def test_list_directory_returns_names_and_types(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "get_macro_indicator.py").write_text("# stub\n")
    (tmp_path / "tools" / "subdir").mkdir()

    entries = list_directory(tmp_path, "tools")

    assert {"name": "get_macro_indicator.py", "type": "file"} in entries
    assert {"name": "subdir", "type": "dir"} in entries


def test_list_directory_rejects_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "clone"
    root.mkdir()
    (tmp_path / "secrets.txt").write_text("nope\n")

    with pytest.raises(ResolverToolError):
        list_directory(root, "../")


def test_list_directory_rejects_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "clone"
    root.mkdir()

    with pytest.raises(ResolverToolError):
        list_directory(root, "/etc")


def test_read_file_returns_contents(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    body = "ALLOWED_INDICATORS = {'gdp_current_usd', 'debt_percent_gdp'}\n"
    (tmp_path / "tools" / "get_macro_indicator.py").write_text(body)

    assert read_file(tmp_path, "tools/get_macro_indicator.py") == body


def test_read_file_rejects_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "clone"
    root.mkdir()
    (tmp_path / "secrets.txt").write_text("nope\n")

    with pytest.raises(ResolverToolError):
        read_file(root, "../secrets.txt")


def test_read_file_rejects_directory(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()

    with pytest.raises(ResolverToolError):
        read_file(tmp_path, "tools")


def test_search_files_finds_pattern_with_line_numbers(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "macro.py").write_text(
        "import x\n"
        "ALLOWED_INDICATORS = {\n"
        "    'gdp_current_usd',\n"
        "    'debt_percent_gdp',\n"
        "}\n"
    )
    (tmp_path / "tools" / "news.py").write_text("# unrelated\n")

    matches = search_files(tmp_path, pattern=r"ALLOWED_INDICATORS")

    assert len(matches) == 1
    hit = matches[0]
    assert hit["path"] == "tools/macro.py"
    assert hit["line_number"] == 2
    assert "ALLOWED_INDICATORS" in hit["line"]


def test_search_files_respects_glob_filter(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "macro.py").write_text("MARKER\n")
    (tmp_path / "tools" / "macro.txt").write_text("MARKER\n")

    matches = search_files(tmp_path, pattern="MARKER", glob="**/*.py")

    assert [m["path"] for m in matches] == ["tools/macro.py"]


def test_search_files_rejects_invalid_regex(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("ok\n")

    with pytest.raises(ResolverToolError):
        search_files(tmp_path, pattern="[unclosed")


def test_read_file_truncates_at_max_bytes(tmp_path: Path) -> None:
    body = "x" * 1000
    (tmp_path / "big.py").write_text(body)

    result = read_file(tmp_path, "big.py", max_bytes=100)

    assert result.startswith("x" * 100)
    assert "truncated" in result.lower()
    assert len(result) > 100  # original 100 bytes plus truncation marker


def test_list_directory_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "clone"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.txt").write_text("leak\n")
    (root / "back").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ResolverToolError):
        list_directory(root, "back")
