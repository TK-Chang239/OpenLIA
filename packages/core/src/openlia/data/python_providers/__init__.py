"""Pure-Python provider runtime expansion — DEFERRED.

Per data-provider-design.md §"Python Providers", this layer lets users
register an adapter implemented as a sandboxed Python function (not an
HTTP/MCP backend). Deferred to a follow-up phase.
"""

__deferred__ = True


def register_python_provider(*_args: object, **_kwargs: object) -> object:  # pragma: no cover
    raise NotImplementedError(
        "openlia.data.python_providers is a deferred subsystem; see "
        "data-provider-design.md Implementation Status section for the owning phase"
    )
