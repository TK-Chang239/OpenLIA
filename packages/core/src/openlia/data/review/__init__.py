"""AI provider-mapping review — DEFERRED.

Per data-provider-design.md §"AI Review", this layer asks an LLM to choose
between configured providers when multiple satisfy the same requirement.
Plan 3 ships only the deterministic resolver; this module is a marker for
the future LLM-driven path.
"""

__deferred__ = True


def run_review(*_args: object, **_kwargs: object) -> object:  # pragma: no cover
    raise NotImplementedError(
        "openlia.data.review is a deferred subsystem; see data-provider-design.md "
        "Implementation Status section for the owning phase"
    )
