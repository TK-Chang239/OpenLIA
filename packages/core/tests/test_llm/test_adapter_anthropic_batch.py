"""AnthropicBatchTransport — Message Batches API."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from openlia.llm.adapters.anthropic_batch import AnthropicBatchTransport
from openlia.llm.batch_transport import BatchRequestItem, BatchStatus
from openlia.llm.types import LLMRequest, Message, ProviderCredentials

_BASE = "https://api.anthropic.com"


def _transport(model: str = "claude-sonnet-4-6") -> AnthropicBatchTransport:
    return AnthropicBatchTransport(
        credentials=ProviderCredentials(api_key="sk-ant-test", base_url=None),
        model=model,
    )


def _item(custom_id: str, text: str) -> BatchRequestItem:
    return BatchRequestItem(
        custom_id=custom_id,
        request=LLMRequest(messages=[Message(role="user", content=text)]),
    )


def _message_body(text: str) -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 7, "output_tokens": 4, "cache_read_input_tokens": 2},
    }


@pytest.mark.asyncio
async def test_submit_batch_posts_requests_and_returns_id():
    captured: dict = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "msgbatch_1", "processing_status": "in_progress"})

    with respx.mock() as mock:
        mock.post(f"{_BASE}/v1/messages/batches").mock(side_effect=_capture)
        batch_id = await _transport().submit_batch([_item("r1", "hi"), _item("r2", "yo")])

    assert batch_id == "msgbatch_1"
    reqs = captured["body"]["requests"]
    assert [r["custom_id"] for r in reqs] == ["r1", "r2"]
    # params is a standard /v1/messages body (model + messages), no stream flag.
    assert reqs[0]["params"]["model"] == "claude-sonnet-4-6"
    assert reqs[0]["params"]["messages"][0]["role"] == "user"
    assert "stream" not in reqs[0]["params"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("processing_status", "expected"),
    [
        ("in_progress", BatchStatus.IN_PROGRESS),
        ("canceling", BatchStatus.IN_PROGRESS),
        ("ended", BatchStatus.COMPLETED),
        ("something_new", BatchStatus.IN_PROGRESS),
    ],
)
async def test_poll_batch_maps_processing_status(processing_status, expected):
    with respx.mock() as mock:
        mock.get(f"{_BASE}/v1/messages/batches/msgbatch_1").mock(
            return_value=httpx.Response(200, json={"processing_status": processing_status})
        )
        assert await _transport().poll_batch("msgbatch_1") == expected


@pytest.mark.asyncio
async def test_fetch_results_maps_succeeded_and_errored():
    results_url = f"{_BASE}/v1/messages/batches/msgbatch_1/results"
    lines = "\n".join(
        [
            json.dumps(
                {
                    "custom_id": "r1",
                    "result": {"type": "succeeded", "message": _message_body("hello")},
                }
            ),
            json.dumps(
                {
                    "custom_id": "r2",
                    "result": {
                        "type": "errored",
                        "error": {"type": "error", "error": {"message": "overloaded"}},
                    },
                }
            ),
            json.dumps({"custom_id": "r3", "result": {"type": "expired"}}),
        ]
    )

    with respx.mock() as mock:
        mock.get(f"{_BASE}/v1/messages/batches/msgbatch_1").mock(
            return_value=httpx.Response(
                200, json={"processing_status": "ended", "results_url": results_url}
            )
        )
        mock.get(results_url).mock(return_value=httpx.Response(200, text=lines))
        results = await _transport().fetch_results("msgbatch_1")

    assert set(results) == {"r1", "r2", "r3"}
    assert results["r1"].response is not None
    assert results["r1"].response.text == "hello"
    assert results["r1"].response.cached_input_tokens == 2
    assert results["r2"].response is None
    assert results["r2"].error == "overloaded"
    assert results["r3"].response is None
    assert results["r3"].error == "expired"


@pytest.mark.asyncio
async def test_fetch_results_no_url_returns_empty():
    with respx.mock() as mock:
        mock.get(f"{_BASE}/v1/messages/batches/msgbatch_2").mock(
            return_value=httpx.Response(200, json={"processing_status": "in_progress"})
        )
        assert await _transport().fetch_results("msgbatch_2") == {}


@pytest.mark.asyncio
async def test_submit_batch_empty_raises():
    with pytest.raises(ValueError, match="no items"):
        await _transport().submit_batch([])
