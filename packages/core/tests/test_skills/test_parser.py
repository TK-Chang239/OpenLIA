import pytest
from openlia.skills import parse_skill_md, serialize_skill_md

VALID_SKILL_MD = """---
name: equity-toolkit
display_name: Equity Toolkit
description: A small DCF playbook.
version: "1.0.0"
departments: [equity_research]
author: Acme
---

# How to use

Body content here.
"""


def test_parse_minimal_skill_md():
    manifest, body = parse_skill_md(VALID_SKILL_MD)
    assert manifest.name == "equity-toolkit"
    assert manifest.display_name == "Equity Toolkit"
    assert manifest.description == "A small DCF playbook."
    assert manifest.version == "1.0.0"
    assert manifest.departments == ["equity_research"]
    assert manifest.author == "Acme"
    assert body.lstrip().startswith("# How to use")


def test_parse_rejects_invalid_skill_id():
    bad = VALID_SKILL_MD.replace("equity-toolkit", "Equity Toolkit!")
    with pytest.raises(ValueError, match="invalid skill id"):
        parse_skill_md(bad)


def test_parse_rejects_missing_departments():
    bad = VALID_SKILL_MD.replace("departments: [equity_research]\n", "")
    with pytest.raises(ValueError, match="departments"):
        parse_skill_md(bad)


def test_parse_accepts_wildcard_departments():
    text = VALID_SKILL_MD.replace("[equity_research]", '["*"]')
    manifest, _ = parse_skill_md(text)
    assert manifest.departments == ["*"]


def test_serialize_round_trips():
    manifest, body = parse_skill_md(VALID_SKILL_MD)
    text = serialize_skill_md(manifest, body)
    manifest2, body2 = parse_skill_md(text)
    assert manifest2.model_dump() == manifest.model_dump()
    assert body2.strip() == body.strip()


def test_parse_rejects_no_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill_md("just a body, no frontmatter\n")
