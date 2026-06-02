"""OpenAIBatchTransport — Files + Batches API over /v1/responses."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from openlia.llm.adapters.openai_batch import OpenAIBatchTransport
from openlia.llm.batch_transport import BatchRequestItem, BatchStatus
from openlia.llm.types import LLMRequest, Message, ProviderCredentials

_BASE = "https://api.openai.com"


def _transport(model: str = "gpt-5.4-2026-03-05") -> OpenAIBatchTransport:
    return OpenAIBatchTransport(
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model=model,
    )


def _item(custom_id: str, text: str) -> BatchRequestItem:
    return BatchRequestItem(
        custom_id=custom_id,
        request=LLMRequest(messages=[Message(role="user", content=text)]),
    )


def _responses_body(text: str) -> dict:
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


@pytest.mark.asyncio
async def test_submit_batch_uploads_jsonl_and_creates_batch():
    captured: dict = {}

    def _capture_upload(request: httpx.Request) -> httpx.Response:
        captured["upload_body"] = request.content
        return httpx.Response(200, json={"id": "file-in-1"})

    def _capture_create(request: httpx.Request) -> httpx.Response:
        captured["create_body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "batch-1", "status": "validating"})

    with respx.mock() as mock:
        mock.post(f"{_BASE}/v1/files").mock(side_effect=_capture_upload)
        mock.post(f"{_BASE}/v1/batches").mock(side_effect=_capture_create)
        batch_id = await _transport().submit_batch([_item("r1", "hi"), _item("r2", "yo")])

    assert batch_id == "batch-1"
    # The uploaded multipart body embeds the JSONL: both custom_ids + the
    # /v1/responses url appear, one line per run.
    body = captured["upload_body"]
    assert b'"custom_id": "r1"' in body
    assert b'"custom_id": "r2"' in body
    assert b"/v1/responses" in body
    # The create call points the batch at the uploaded file + responses endpoint.
    assert captured["create_body"]["input_file_id"] == "file-in-1"
    assert captured["create_body"]["endpoint"] == "/v1/responses"
    assert captured["create_body"]["completion_window"] == "24h"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_status", "expected"),
    [
        ("validating", BatchStatus.IN_PROGRESS),
        ("in_progress", BatchStatus.IN_PROGRESS),
        ("finalizing", BatchStatus.IN_PROGRESS),
        ("completed", BatchStatus.COMPLETED),
        ("failed", BatchStatus.FAILED),
        ("cancelled", BatchStatus.FAILED),
        ("expired", BatchStatus.EXPIRED),
        ("something_new", BatchStatus.IN_PROGRESS),
    ],
)
async def test_poll_batch_maps_status(provider_status, expected):
    with respx.mock() as mock:
        mock.get(f"{_BASE}/v1/batches/batch-1").mock(
            return_value=httpx.Response(200, json={"status": provider_status})
        )
        assert await _transport().poll_batch("batch-1") == expected


@pytest.mark.asyncio
async def test_fetch_results_maps_ok_and_error_by_custom_id():
    output_lines = "\n".join(
        [
            json.dumps(
                {
                    "custom_id": "r1",
                    "response": {"status_code": 200, "body": _responses_body("hello")},
                    "error": None,
                }
            ),
            json.dumps(
                {
                    "custom_id": "r2",
                    "response": {"status_code": 400, "body": {"error": "bad"}},
                    "error": None,
                }
            ),
        ]
    )

    with respx.mock() as mock:
        mock.get(f"{_BASE}/v1/batches/batch-1").mock(
            return_value=httpx.Response(
                200, json={"status": "completed", "output_file_id": "file-out-1"}
            )
        )
        mock.get(f"{_BASE}/v1/files/file-out-1/content").mock(
            return_value=httpx.Response(200, text=output_lines)
        )
        results = await _transport().fetch_results("batch-1")

    assert set(results) == {"r1", "r2"}
    assert results["r1"].error is None
    assert results["r1"].response is not None
    assert results["r1"].response.text == "hello"
    assert results["r2"].response is None
    assert "http 400" in results["r2"].error


@pytest.mark.asyncio
async def test_fetch_results_reads_error_file():
    with respx.mock() as mock:
        mock.get(f"{_BASE}/v1/batches/batch-2").mock(
            return_value=httpx.Response(
                200, json={"status": "completed", "error_file_id": "file-err-1"}
            )
        )
        mock.get(f"{_BASE}/v1/files/file-err-1/content").mock(
            return_value=httpx.Response(
                200,
                text=json.dumps(
                    {"custom_id": "r9", "error": {"message": "rate limited"}}
                ),
            )
        )
        results = await _transport().fetch_results("batch-2")

    assert results["r9"].response is None
    assert results["r9"].error == "rate limited"


@pytest.mark.asyncio
async def test_submit_batch_empty_raises():
    with pytest.raises(ValueError, match="no items"):
        await _transport().submit_batch([])
