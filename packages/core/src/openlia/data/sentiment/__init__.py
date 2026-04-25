"""Retail-sentiment availability checker — DEFERRED.

Per data-provider-design.md §"Retail Sentiment", this layer reports whether
configured providers can satisfy retail-sentiment requirements (Reddit, X,
StockTwits). Deferred to the Retail Sentiment department phase.
"""

__deferred__ = True


def check_availability(*_args: object, **_kwargs: object) -> object:  # pragma: no cover
    raise NotImplementedError(
        "openlia.data.sentiment is a deferred subsystem; see data-provider-design.md "
        "Implementation Status section for the owning phase"
    )
