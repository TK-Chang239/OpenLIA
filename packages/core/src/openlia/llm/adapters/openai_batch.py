"""OpenAI Batch API transport for the Responses endpoint.

Implements ``BatchTransport`` against OpenAI's Files + Batches APIs,
targeting ``/v1/responses`` so batched turns are byte-identical to the
live ``OpenAIResponsesAdapter`` (both build bodies via
``build_responses_payload`` and parse via ``parse_responses_body``).

Flow:
  submit_batch  -> upload a JSONL input file (one line per run) then
                   POST /v1/batches; return the batch id.
  poll_batch    -> GET /v1/batches/{id}; normalize ``status``.
  fetch_results -> GET the output (+ error) file content; map each line
                   back to its ``custom_id``.
  cancel_batch  -> POST /v1/batches/{id}/cancel.
"""

from __future__ import annotations

import json
import logging

from openlia.llm.adapters._http import (
    TRANSIENT_NETWORK_ERRORS,
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.adapters.openai_responses import (
    build_responses_payload,
    parse_responses_body,
)
from openlia.llm.batch_transport import (
    BatchRequestItem,
    BatchResultItem,
    BatchStatus,
)
from openlia.llm.retry import with_retries
from openlia.llm.types import ProviderCredentials

log = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.openai.com"
_RESPONSES_URL = "/v1/responses"

# OpenAI batch ``status`` -> normalized BatchStatus. Unknown / unlisted
# statuses keep IN_PROGRESS so the orchestrator's wall-clock deadline (not
# an unexpected status string) decides when to give up.
_STATUS_MAP: dict[str, BatchStatus] = {
    "validating": BatchStatus.IN_PROGRESS,
    "in_progress": BatchStatus.IN_PROGRESS,
    "finalizing": BatchStatus.IN_PROGRESS,
    "cancelling": BatchStatus.IN_PROGRESS,
    "completed": BatchStatus.COMPLETED,
    "failed": BatchStatus.FAILED,
    "cancelled": BatchStatus.FAILED,
    "expired": BatchStatus.EXPIRED,
}


class OpenAIBatchTransport:
    """``BatchTransport`` over OpenAI Files + Batches for /v1/responses."""

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        base_url: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._model = model
        self._base_url = base_url or credentials.base_url or _DEFAULT_BASE_URL

    def _auth_header(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self._credentials.api_key}"}

    def _json_headers(self) -> dict[str, str]:
        return {**self._auth_header(), "content-type": "application/json"}

    def _build_input_jsonl(self, items: list[BatchRequestItem]) -> bytes:
        lines = [
            json.dumps(
                {
                    "custom_id": item.custom_id,
                    "method": "POST",
                    "url": _RESPONSES_URL,
                    "body": build_responses_payload(self._model, item.request),
                }
            )
            for item in items
        ]
        return ("\n".join(lines) + "\n").encode("utf-8")

    async def submit_batch(self, items: list[BatchRequestItem]) -> str:
        if not items:
            raise ValueError("submit_batch called with no items")
        jsonl = self._build_input_jsonl(items)

        async def _upload() -> dict:
            # No explicit content-type: httpx sets the multipart boundary.
            async with make_client(base_url=self._base_url, headers=self._auth_header()) as client:
                try:
                    resp = await client.post(
                        "/v1/files",
                        files={"file": ("batch.jsonl", jsonl, "application/jsonl")},
                        data={"purpose": "batch"},
                    )
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.json()

        file_body = await with_retries(_upload)
        input_file_id = file_body["id"]

        async def _create() -> dict:
            async with make_client(base_url=self._base_url, headers=self._json_headers()) as client:
                try:
                    resp = await client.post(
                        "/v1/batches",
                        json={
                            "input_file_id": input_file_id,
                            "endpoint": _RESPONSES_URL,
                            "completion_window": "24h",
                        },
                    )
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.json()

        batch_body = await with_retries(_create)
        return batch_body["id"]

    async def _get_batch(self, batch_id: str) -> dict:
        async def _call() -> dict:
            async with make_client(base_url=self._base_url, headers=self._json_headers()) as client:
                try:
                    resp = await client.get(f"/v1/batches/{batch_id}")
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.json()

        return await with_retries(_call)

    async def poll_batch(self, batch_id: str) -> BatchStatus:
        body = await self._get_batch(batch_id)
        status = str(body.get("status", ""))
        mapped = _STATUS_MAP.get(status)
        if mapped is None:
            log.warning("openai batch %s: unknown status %r -> IN_PROGRESS", batch_id, status)
            return BatchStatus.IN_PROGRESS
        return mapped

    async def _get_file_content(self, file_id: str) -> str:
        async def _call() -> str:
            async with make_client(base_url=self._base_url, headers=self._json_headers()) as client:
                try:
                    resp = await client.get(f"/v1/files/{file_id}/content")
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.text

        return await with_retries(_call)

    async def fetch_results(self, batch_id: str) -> dict[str, BatchResultItem]:
        body = await self._get_batch(batch_id)
        results: dict[str, BatchResultItem] = {}

        output_file_id = body.get("output_file_id")
        if output_file_id:
            content = await self._get_file_content(output_file_id)
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                results.update(_parse_output_line(line))

        error_file_id = body.get("error_file_id")
        if error_file_id:
            content = await self._get_file_content(error_file_id)
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                cid = entry.get("custom_id")
                if cid and cid not in results:
                    results[cid] = BatchResultItem(
                        custom_id=cid,
                        response=None,
                        error=_error_text(entry),
                    )
        return results

    async def cancel_batch(self, batch_id: str) -> None:
        async with make_client(base_url=self._base_url, headers=self._json_headers()) as client:
            try:
                await client.post(f"/v1/batches/{batch_id}/cancel")
            except TRANSIENT_NETWORK_ERRORS as exc:
                raise wrap_httpx_error(exc) from exc


def _parse_output_line(line: str) -> dict[str, BatchResultItem]:
    """Map one output-file JSONL line to ``{custom_id: BatchResultItem}``."""
    entry = json.loads(line)
    cid = entry.get("custom_id")
    if not cid:
        return {}
    if entry.get("error"):
        return {cid: BatchResultItem(custom_id=cid, response=None, error=_error_text(entry))}
    response = entry.get("response") or {}
    status_code = response.get("status_code")
    response_body = response.get("body")
    if status_code != 200 or not isinstance(response_body, dict):
        return {
            cid: BatchResultItem(
                custom_id=cid,
                response=None,
                error=f"http {status_code}: {json.dumps(response_body, default=str)[:300]}",
            )
        }
    return {
        cid: BatchResultItem(
            custom_id=cid,
            response=parse_responses_body(response_body),
            error=None,
        )
    }


def _error_text(entry: dict) -> str:
    err = entry.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("code") or json.dumps(err, default=str)[:300])
    return str(err) if err is not None else "unknown batch error"


__all__ = ["OpenAIBatchTransport"]
