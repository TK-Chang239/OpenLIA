"""P1-14 — startup prompt slot validation.

`_make_lifespan` constructs a `PromptLoader` and calls
`validate_department_slots` per configured department before `yield`. A
missing slot raises `PromptSlotNotFound`, propagating out of lifespan and
preventing the server from starting.
"""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.prompts import PromptSlotNotFound


def _write_full_prompts(root: Path) -> None:
    """Mirror the shipped prompt structure with every required slot present."""
    shared = root / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "voice.yaml.j2").write_text("clear, professional tone\n")
    (shared / "output_discipline.yaml.j2").write_text("Output discipline: be concise.\n")
    (root / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: You are the Secretary.
              welcome: hi
            """
        )
    )
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            chat:
              system: ER chat.
            report:
              system: ER report.
              stock_initiation:
                user: stock init
              stock_update:
                user: stock update
              sector_research:
                user: sector research
            """
        )
    )
    (root / "earnings_update.yaml").write_text(
        dedent(
            """\
            report:
              system: EU report.
              earnings_update:
                user: eu user
            """
        )
    )
    (root / "morning_briefing.yaml").write_text(
        dedent(
            """\
            report:
              system: MB report.
              morning_briefing:
                user: mb user
            """
        )
    )
    (root / "macro_research.yaml").write_text(
        dedent(
            """\
            batch:
              t4_assessment:
                system: t4 system
                user: t4 user
              t5_assessment:
                system: t5 system
                user: t5 user
            """
        )
    )
    (root / "retail_sentiment.yaml").write_text(
        dedent(
            """\
            batch:
              classify_sentiment:
                system: rs system
                user: rs user
            """
        )
    )


def test_lifespan_validates_real_prompts_clean_boot(tmp_path: Path) -> None:
    """Control case: with the shipped prompts (default root), the server
    boots cleanly and serves /health 200."""
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "0",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200


def test_lifespan_raises_on_missing_slot(tmp_path: Path) -> None:
    """Negative case: with a deliberately renamed slot in a tmp prompts dir,
    the lifespan validation raises `PromptSlotNotFound` before yield."""
    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    _write_full_prompts(prompts_root)
    # Delete the secretary `chat.welcome` slot (kept the file, dropped the slot).
    (prompts_root / "secretary.yaml").write_text(
        dedent(
            """\
            chat:
              system: You are the Secretary.
            """
        )
    )

    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "0",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        # Inject the broken root before lifespan runs.
        app.state.prompt_root = prompts_root

        with pytest.raises(PromptSlotNotFound):
            with TestClient(app):
                pass
