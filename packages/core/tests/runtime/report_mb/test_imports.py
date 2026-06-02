def test_public_surface_imports():
    from openlia.llm.runtime.report_mb import (
        BriefingContext,
        MbDataTransports,
        Runner,
        RunRequest,
        RunResult,
        TemplateSpec,
    )

    assert BriefingContext is not None
    assert MbDataTransports is not None
    assert RunRequest is not None
    assert RunResult is not None
    assert Runner is not None
    assert TemplateSpec is not None
