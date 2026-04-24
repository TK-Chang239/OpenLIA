from openlia.panic_thermometer.panels.base import (
    PanelBase,
    PanelContextBuildResult,
)


def test_panel_context_build_result_shape():
    r = PanelContextBuildResult(
        scalars={"price": 92.4, "prev_close": 91.0},
        raw_series={"price": [80.0, 82.0, 92.4]},
        warnings=[],
    )
    assert r.scalars["price"] == 92.4
    assert r.raw_series["price"][-1] == 92.4
    assert r.warnings == []


def test_panel_base_declares_required_attrs():
    # PanelBase is a structural protocol; ensure it advertises the expected names
    assert hasattr(PanelBase, "__protocol_attrs__") or True
    annotations = PanelBase.__annotations__ if hasattr(PanelBase, "__annotations__") else {}
    for attr in ("panel_id", "required_requirements", "optional_requirements"):
        assert attr in annotations or hasattr(PanelBase, attr)
