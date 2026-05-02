"""Wraps the official `xdk` Python SDK with a flat method surface usable
by the connector subsystem's python_lib transport.

The native SDK groups methods under nested resources (e.g.
`client.posts.search_recent`, `client.users.get_by_username`); the
transport only walks top-level methods on the instance via
`inspect.getmembers`. We expose flat passthrough methods so the chat
LLM can see them in `list_tools()` and call them directly.

Live-verified against api.x.com on 2026-05-01 with the user's bearer
token. Returns flattened `list[dict]` so dispatch and downstream
prompts don't need to know about the SDK's pagination iterators.
"""

from __future__ import annotations

from typing import Any

from xdk import Client


class XClient(Client):
    """`xdk.Client` plus flat passthroughs for the most common
    social-listening calls.

    All methods auto-paginate up to `max_results` items and return a
    plain `list[dict]`.
    """

    def search_recent_posts(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search posts from the last 7 days matching the X-search query.

        The X recent-search endpoint requires `max_results` between 10
        and 100; values below 10 are silently clamped up to 10.

        See https://docs.x.com/x-api/posts/search/quickstart/recent-search
        for query syntax.
        """
        per_page = max(10, min(max_results, 100))
        out: list[dict[str, Any]] = []
        for page in self.posts.search_recent(query=query, max_results=per_page):
            if not page.data:
                continue
            for item in page.data:
                out.append(_to_dict(item))
                if len(out) >= max_results:
                    return out
        return out

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch a single user record by handle (without the leading @)."""
        resp = self.users.get_by_username(username=username)
        data = getattr(resp, "data", None)
        if data is None:
            return None
        return _to_dict(data)


def _to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        return dump()
    return dict(vars(item))


__all__ = ["XClient"]
