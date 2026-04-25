"""Runtime dispatch router — DEFERRED.

Per data-provider-design.md §"Runtime Dispatch", this layer wraps adapter
calls with retry/backoff coordination across providers, falls back when a
provider raises DataNotAvailable, and emits SSE tool_result events. Plan 5
implements it; this module is the namespace placeholder.
"""

__deferred__ = True


def dispatch(*_args: object, **_kwargs: object) -> object:  # pragma: no cover
    raise NotImplementedError(
        "openlia.data.dispatch is a deferred subsystem; see data-provider-design.md "
        "Implementation Status section for the owning phase"
    )
