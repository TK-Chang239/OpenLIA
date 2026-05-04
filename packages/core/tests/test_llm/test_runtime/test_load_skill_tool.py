from openlia.llm.runtime.events import ChatSkillLoaded
from openlia.llm.runtime.tools import LOAD_SKILL_SCHEMA


def test_chat_skill_loaded_to_wire():
    e = ChatSkillLoaded(message_id="m1", skill_id="alpha", display_name="Alpha")
    wire = {"type": e.TYPE, **{k: v for k, v in vars(e).items()}}
    assert wire["type"] == "chat.skill_loaded"
    assert wire["skill_id"] == "alpha"


def test_load_skill_schema_shape():
    assert LOAD_SKILL_SCHEMA.name == "load_skill"
    assert "skill_id" in LOAD_SKILL_SCHEMA.parameters["properties"]
    assert LOAD_SKILL_SCHEMA.parameters["required"] == ["skill_id"]
