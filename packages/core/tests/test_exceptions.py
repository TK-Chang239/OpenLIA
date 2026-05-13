def test_model_not_configured_error_exists_with_slot_id():
    from openlia.llm.exceptions import ModelNotConfiguredError

    e = ModelNotConfiguredError(slot_kind="department", slot_id="secretary")
    assert e.slot_kind == "department"
    assert e.slot_id == "secretary"
    assert "secretary" in str(e)
    assert "Settings" in str(e)


def test_tier_not_configured_error_removed():
    import openlia.llm.exceptions as exc

    assert not hasattr(exc, "TierNotConfiguredError")
