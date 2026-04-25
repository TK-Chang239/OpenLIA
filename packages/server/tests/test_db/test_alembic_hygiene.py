"""Alembic + module-hygiene guards.

Covers audit items P1-1a-02 (autogenerate-clean against current ORM) and
P2-04 / P2-1a-01 (every db module has a module docstring).
"""

from __future__ import annotations

import ast
import importlib
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT_SERVER = Path(__file__).resolve().parents[2]  # packages/server
VERSIONS_DIR = (
    REPO_ROOT_SERVER
    / "src"
    / "openlia_server"
    / "db"
    / "migrations"
    / "versions"
)
DB_PKG_ROOT = REPO_ROOT_SERVER / "src" / "openlia_server" / "db"


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    merged["OPENLIA_DB_URL"] = db_url
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT_SERVER,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


_RS_SNAPSHOT_INDEX_DIFF_REASON = (
    "SQLite reflection cannot recover a text-expression index direction "
    "('captured_at DESC'), so alembic autogenerate always re-issues the "
    "drop/create pair for ix_rs_snapshots_ticker_captured even when the "
    "underlying schema is correct. This is a known Alembic+SQLite "
    "limitation and does not represent real ORM-vs-migration drift."
)


def _extract_body(file_path: Path, func_name: str) -> str:
    tree = ast.parse(file_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            body_statements = [
                stmt
                for stmt in node.body
                if not (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                )
            ]
            body_statements = [
                stmt
                for stmt in body_statements
                if not _is_rs_snapshot_index_statement(stmt)
            ]
            if not body_statements or (
                len(body_statements) == 1
                and isinstance(body_statements[0], ast.Pass)
            ):
                return ""
            return ast.unparse(ast.Module(body=body_statements, type_ignores=[]))
    raise AssertionError(f"function {func_name} not found in {file_path}")


def _is_rs_snapshot_index_statement(stmt: ast.stmt) -> bool:
    """Whitelist the known-benign rs_snapshots DESC-index roundtrip noise."""
    if not isinstance(stmt, ast.With):
        return False
    source = ast.unparse(stmt)
    return (
        "batch_alter_table('rs_snapshots'" in source
        and "ix_rs_snapshots_ticker_captured" in source
    )


def test_alembic_autogenerate_is_clean(tmp_path: Path) -> None:
    """`alembic revision --autogenerate` against the shipped ORM must emit
    an empty upgrade/downgrade body. Any drift between models and the live
    schema surfaces here. Temp revision is deleted at the end."""
    db_file = tmp_path / "clean.db"
    db_url = f"sqlite:///{db_file}"

    up = _run_alembic(["upgrade", "head"], db_url)
    assert up.returncode == 0, up.stderr

    before = {p.name for p in VERSIONS_DIR.glob("*.py")}
    try:
        proc = _run_alembic(
            ["revision", "--autogenerate", "-m", "parity-check"],
            db_url,
        )
        assert proc.returncode == 0, proc.stderr

        after = {p.name for p in VERSIONS_DIR.glob("*.py")}
        new_files = after - before
        assert len(new_files) == 1, f"expected exactly one new revision file, got {new_files}"
        new_file = VERSIONS_DIR / next(iter(new_files))

        upgrade_body = _extract_body(new_file, "upgrade")
        downgrade_body = _extract_body(new_file, "downgrade")
        content = new_file.read_text()
    finally:
        after = {p.name for p in VERSIONS_DIR.glob("*.py")}
        for name in after - before:
            (VERSIONS_DIR / name).unlink()

    assert upgrade_body == "", (
        "autogenerate produced a non-empty upgrade body — ORM has drifted from "
        f"the shipped migrations. Generated file:\n{content}"
    )
    assert downgrade_body == "", (
        "autogenerate produced a non-empty downgrade body — ORM has drifted "
        f"from the shipped migrations. Generated file:\n{content}"
    )


_TIMESTAMP_RE = re.compile(r"^\d{4}[-_]\d{2}[-_]\d{2}[-_]\d{4}_")


def _iter_db_module_files() -> list[Path]:
    """First-party db/*.py files except Alembic-generated migrations and the
    Alembic `env.py` (env.py only runs inside an `alembic` process)."""
    out: list[Path] = []
    for path in DB_PKG_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if "versions" in path.parts:
            continue
        if path.name == "env.py":
            continue
        out.append(path)
    return out


def _module_name_for(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT_SERVER / "src").with_suffix("")
    return ".".join(rel.parts)


def test_every_db_module_has_docstring() -> None:
    """Module docstrings carry spec-reference anchors that make future audits
    possible. Enforce their presence across the db package."""
    missing: list[str] = []
    for path in _iter_db_module_files():
        module = importlib.import_module(_module_name_for(path))
        if not (module.__doc__ and module.__doc__.strip()):
            missing.append(_module_name_for(path))
    assert not missing, f"modules missing docstrings: {missing}"
