"""BatchOrchestrator — lockstep batches, drop-on-finalize, failure isolation."""

from __future__ import annotations

import pytest
from openlia.llm.batch_transport import BatchResultItem, BatchStatus
from openlia.llm.runtime.batch_orchestrator import BatchOrchestrator
from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.run_state import EuRunState
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors, RunRequest
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec
from openlia.llm.types import LLMResponse, ToolCall


def _req() -> RunRequest:
    return RunRequest(
        subject="MSFT.US",
        template=TemplateSpec(
            template_id="eu_default",
            name="EU",
            shape_description="scorecard",
            ticker_anchored=True,
            default_length="normal",
            sections=[SectionSpec(id="quick_take", title="Quick Take", intent="TLDR")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset(), web_search=False),
    )


def _transports() -> EuDataTransports:
    return EuDataTransports(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [],
        news=lambda t, n: [],
        earnings_calendar=lambda t: [],
    )


def _state(custom_id: str) -> EuRunState:
    return EuRunState.from_request(_req(), transports=_transports(), custom_id=custom_id)


def _write(section: str = "quick_take") -> LLMResponse:
    return LLMResponse(
        text="",
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[
            ToolCall(
                id="c1", name="write_section", arguments={"section_id": section, "markdown": "b."}
            )
        ],
    )


def _finalize() -> LLMResponse:
    return LLMResponse(
        text="",
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[ToolCall(id="c2", name="finalize", arguments={})],
    )


class FakeBatchTransport:
    """Per-custom_id scripted responses; optional per-run hard errors."""

    def __init__(self, scripts: dict[str, list[LLMResponse]], errors: dict[str, str] | None = None):
        self._scripts = {k: iter(v) for k, v in scripts.items()}
        self._errors = errors or {}
        self._pending: dict[str, list[str]] = {}
        self._n = 0
        self.submitted: list[set[str]] = []
        self.poll_status = BatchStatus.COMPLETED

    async def submit_batch(self, items):
        self._n += 1
        bid = f"batch-{self._n}"
        cids = [it.custom_id for it in items]
        self._pending[bid] = cids
        self.submitted.append(set(cids))
        return bid

    async def poll_batch(self, batch_id):
        return self.poll_status

    async def fetch_results(self, batch_id):
        out: dict[str, BatchResultItem] = {}
        for cid in self._pending.get(batch_id, []):
            if cid in self._errors:
                out[cid] = BatchResultItem(custom_id=cid, response=None, error=self._errors[cid])
                continue
            try:
                resp = next(self._scripts[cid])
            except StopIteration:
                out[cid] = BatchResultItem(custom_id=cid, response=None, error="script exhausted")
                continue
            out[cid] = BatchResultItem(custom_id=cid, response=resp, error=None)
        return out

    async def cancel_batch(self, batch_id):
        return None


async def _noop_sleep(_seconds: float) -> None:
    return None


def _counter():
    state = {"t": 0.0}

    def _now() -> float:
        state["t"] += 1.0
        return state["t"]

    return _now


@pytest.mark.asyncio
async def test_runs_finish_at_different_turns_and_batches_shrink():
    a, b, c = _state("A"), _state("B"), _state("C")
    transport = FakeBatchTransport(
        scripts={
            "A": [_write(), _finalize()],  # 2 turns
            "B": [_write(), _write(), _finalize()],  # 3 turns
            "C": [],  # errored cycle 1
        },
        errors={"C": "rate limited"},
    )
    completed: list[str] = []
    failed: list[tuple[str, str]] = []
    persisted: list[str] = []

    orch = BatchOrchestrator(
        transport=transport,
        runs=[a, b, c],
        poll_interval_s=0,
        max_wait_s=10_000,
        on_turn_persisted=lambda bid, active: persisted.append(bid),
        on_run_complete=lambda cid, result: completed.append(cid),
        on_run_failed=lambda cid, msg: failed.append((cid, msg)),
        sleep=_noop_sleep,
        now=_counter(),
    )
    await orch.run()

    assert sorted(completed) == ["A", "B"]
    assert [cid for cid, _ in failed] == ["C"]
    assert failed[0][1] == "rate limited"
    # Batch 1 had all three; later batches shrink as runs finalize.
    assert transport.submitted[0] == {"A", "B", "C"}
    assert transport.submitted[1] == {"A", "B"}
    assert transport.submitted[2] == {"B"}
    assert len(transport.submitted) == 3


@pytest.mark.asyncio
async def test_batch_level_failure_fails_all_active():
    a, b = _state("A"), _state("B")
    transport = FakeBatchTransport(scripts={"A": [_write()], "B": [_write()]})
    transport.poll_status = BatchStatus.FAILED
    completed: list[str] = []
    failed: list[str] = []

    orch = BatchOrchestrator(
        transport=transport,
        runs=[a, b],
        poll_interval_s=0,
        max_wait_s=10_000,
        on_run_complete=lambda cid, result: completed.append(cid),
        on_run_failed=lambda cid, msg: failed.append(cid),
        sleep=_noop_sleep,
        now=_counter(),
    )
    await orch.run()

    assert completed == []
    assert sorted(failed) == ["A", "B"]


@pytest.mark.asyncio
async def test_resume_from_existing_batch_then_continues():
    # A was mid-run (quick_take written) when the process crashed; the
    # finalize-turn batch "batch-resumed" was already in flight.
    a = _state("A")
    a.pending_request()
    await a.apply_response(_write())

    transport = FakeBatchTransport(scripts={"A": [_write(), _finalize()]})
    # Pre-seed the in-flight batch as if submitted before the crash.
    transport._pending["batch-resumed"] = ["A"]
    completed: list[str] = []

    orch = BatchOrchestrator(
        transport=transport,
        runs=[a],
        poll_interval_s=0,
        max_wait_s=10_000,
        on_run_complete=lambda cid, result: completed.append(cid),
        sleep=_noop_sleep,
        now=_counter(),
    )
    await orch.run(resume_batch_id="batch-resumed")

    assert completed == ["A"]
    # The resumed batch was consumed without a new submit; exactly one fresh
    # batch was submitted afterward to carry the finalize turn.
    assert len(transport.submitted) == 1


@pytest.mark.asyncio
async def test_deadline_expiry_fails_all_active():
    a = _state("A")
    transport = FakeBatchTransport(scripts={"A": [_write()]})
    transport.poll_status = BatchStatus.IN_PROGRESS  # never completes
    failed: list[str] = []

    # now() jumps past max_wait on the first poll check.
    times = iter([0.0, 100.0, 200.0, 300.0])

    orch = BatchOrchestrator(
        transport=transport,
        runs=[a],
        poll_interval_s=0,
        max_wait_s=50,
        on_run_failed=lambda cid, msg: failed.append(cid),
        sleep=_noop_sleep,
        now=lambda: next(times),
    )
    await orch.run()

    assert failed == ["A"]
