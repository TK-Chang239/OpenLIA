"""Anthropic Message Batches transport.

Implements ``BatchTransport`` against Anthropic's Message Batches API.
Each batched turn submits the same ``/v1/messages`` params the live
``AnthropicAdapter`` builds (via ``build_messages_payload``) and parses
results with ``parse_messages_body`` — so a batched turn is byte-identical
to a live (non-streamed) turn.

Flow:
  submit_batch  -> POST /v1/messages/batches {requests:[{custom_id, params}]}
  poll_batch    -> GET /v1/messages/batches/{id}; map ``processing_status``
  fetch_results -> GET the batch's ``results_url`` (JSONL); map each line
                   back to its ``custom_id``
  cancel_batch  -> POST /v1/messages/batches/{id}/cancel
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
from openlia.llm.adapters.anthropic import (
    build_messages_payload,
    parse_messages_body,
)
from openlia.llm.batch_transport import (
    BatchRequestItem,
    BatchResultItem,
    BatchStatus,
)
from openlia.llm.retry import with_retries
from openlia.llm.types import ProviderCredentials

log = logging.getLogger(__name__)

_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"

# Anthropic batch ``processing_status`` -> normalized BatchStatus. A batch
# that "ended" is COMPLETED even if individual requests errored/expired
# (those surface per-result in fetch_results). There is no batch-level
# FAILED/EXPIRED. Unknown statuses keep IN_PROGRESS so the orchestrator
# deadline (not an unexpected string) decides when to give up.
_STATUS_MAP: dict[str, BatchStatus] = {
    "in_progress": BatchStatus.IN_PROGRESS,
    "canceling": BatchStatus.IN_PROGRESS,
    "ended": BatchStatus.COMPLETED,
}


class AnthropicBatchTransport:
    """``BatchTransport`` over Anthropic's Message Batches API."""

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        base_url: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._model = model
        self._base_url = base_url or credentials.base_url or _BASE_URL

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._credentials.api_key or "",
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

    async def submit_batch(self, items: list[BatchRequestItem]) -> str:
        if not items:
            raise ValueError("submit_batch called with no items")
        requests = [
            {
                "custom_id": item.custom_id,
                "params": build_messages_payload(self._model, item.request),
            }
            for item in items
        ]

        async def _create() -> dict:
            async with make_client(base_url=self._base_url, headers=self._headers()) as client:
                try:
                    resp = await client.post("/v1/messages/batches", json={"requests": requests})
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.json()

        return (await with_retries(_create))["id"]

    async def _get_batch(self, batch_id: str) -> dict:
        async def _call() -> dict:
            async with make_client(base_url=self._base_url, headers=self._headers()) as client:
                try:
                    resp = await client.get(f"/v1/messages/batches/{batch_id}")
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
        status = str(body.get("processing_status", ""))
        mapped = _STATUS_MAP.get(status)
        if mapped is None:
            log.warning("anthropic batch %s: unknown status %r -> IN_PROGRESS", batch_id, status)
            return BatchStatus.IN_PROGRESS
        return mapped

    async def fetch_results(self, batch_id: str) -> dict[str, BatchResultItem]:
        body = await self._get_batch(batch_id)
        results_url = body.get("results_url")
        if not results_url:
            return {}

        async def _get_results() -> str:
            async with make_client(base_url=self._base_url, headers=self._headers()) as client:
                try:
                    resp = await client.get(results_url)
                except TRANSIENT_NETWORK_ERRORS as exc:
                    raise wrap_httpx_error(exc) from exc
                if resp.status_code != 200:
                    status_to_exception(
                        status_code=resp.status_code,
                        body_text=resp.text,
                        headers=dict(resp.headers),
                    )
                return resp.text

        content = await with_retries(_get_results)
        results: dict[str, BatchResultItem] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            results.update(_parse_result_line(line))
        return results

    async def cancel_batch(self, batch_id: str) -> None:
        async with make_client(base_url=self._base_url, headers=self._headers()) as client:
            try:
                await client.post(f"/v1/messages/batches/{batch_id}/cancel")
            except TRANSIENT_NETWORK_ERRORS as exc:
                raise wrap_httpx_error(exc) from exc


def _parse_result_line(line: str) -> dict[str, BatchResultItem]:
    """Map one results-file JSONL line to ``{custom_id: BatchResultItem}``."""
    entry = json.loads(line)
    cid = entry.get("custom_id")
    if not cid:
        return {}
    result = entry.get("result") or {}
    rtype = result.get("type")
    if rtype == "succeeded":
        message = result.get("message") or {}
        return {
            cid: BatchResultItem(custom_id=cid, response=parse_messages_body(message), error=None)
        }
    return {cid: BatchResultItem(custom_id=cid, response=None, error=_error_text(rtype, result))}


def _error_text(rtype: str | None, result: dict) -> str:
    err = result.get("error")
    if isinstance(err, dict):
        # Anthropic nests as {"type":"error","error":{"type":..,"message":..}}.
        inner = err.get("error") if isinstance(err.get("error"), dict) else err
        return str(inner.get("message") or inner.get("type") or json.dumps(err, default=str)[:300])
    return str(rtype or "unknown batch error")


__all__ = ["AnthropicBatchTransport"]
