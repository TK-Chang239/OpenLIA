from __future__ import annotations

import pytest
from openlia.llm.runtime.section_draft import OpenQuestion, PriorSection, SectionDraft
from pydantic import ValidationError


def test_minimal_draft_validates() -> None:
    d = SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": [{"type": "text", "content": "Microsoft is a software company."}],
            "citations_used": [],
            "word_count": 5,
            "open_questions": [],
        }
    )
    assert d.section_id == "company_overview"
    assert d.word_count == 5


def test_blocks_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        SectionDraft.model_validate(
            {
                "section_id": "x",
                "blocks": [],
                "citations_used": [],
                "word_count": 0,
                "open_questions": [],
            }
        )


def test_prior_section_key_facts_capped_at_five() -> None:
    with pytest.raises(ValidationError):
        PriorSection.model_validate(
            {
                "section_id": "x",
                "title": "X",
                "summary": "...",
                "key_facts_for_threading": [f"f{i}" for i in range(6)],
            }
        )


def test_open_question_shape() -> None:
    q = OpenQuestion.model_validate(
        {"section_id": "risks", "question": "Pending FX exposure detail."}
    )
    assert q.section_id == "risks"
