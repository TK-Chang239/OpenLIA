from __future__ import annotations

import pytest
from openlia_server.services.user_presence_registry import UserPresenceRegistry


@pytest.mark.asyncio
async def test_chat_attached_report_changed_event_delivered_to_subscriber() -> None:
    presence = UserPresenceRegistry()
    q = presence.attach("u_1")
    presence.fanout("u_1", {
        "type": "chat.attached_report_changed",
        "session_id": "sess_test",
        "new_report_id": "r_new",
    })
    ev = q.get_nowait()
    assert ev["type"] == "chat.attached_report_changed"
    assert ev["session_id"] == "sess_test"
    assert ev["new_report_id"] == "r_new"
