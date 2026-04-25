"""Tests for the Retail Sentiment sync classifier wiring.

Covers both branches:
  - No LLM tier configured → neutral fallback, no audits.
  - Tier configured → resolves, builds adapter, emits classified items + one
    ClassificationAudit per batch.

Also asserts that the app factory installs `RefreshingSyncLlmClassifier` on
`app.state.rs_runner._classifier` (replacing the `NeutralClassifier` default).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openlia.llm.types import LLMResponse
from openlia.retail_sentiment.schemas import RawSocialPost
from openlia_server.services import llm_providers as svc
from openlia_server.services.rs_sync_classifier import RefreshingSyncLlmClassifier


@pytest.fixture
def _env_secret(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")


def _post(pid: str, text: str) -> RawSocialPost:
    from datetime import UTC, datetime

    return RawSocialPost(
        id=pid,
        ticker="AAPL",
        source="social_sentiment",
        text=text,
        created_at=datetime.now(UTC),
    )


def test_refreshing_classifier_falls_back_to_neutral_when_no_tier_configured(
    _env_secret, db_session_factory, create_tables
) -> None:
    classifier = RefreshingSyncLlmClassifier(db_session_factory=db_session_factory)
    result = classifier.classify_batch(
        ticker="AAPL",
        posts=[_post("p1", "great quarter"), _post("p2", "meh outlook")],
    )
    assert [item.classification.value for item in result.items] == ["neutral", "neutral"]
    assert result.audits == []


def test_refreshing_classifier_uses_configured_model(
    _env_secret, db_session, db_session_factory, create_tables
) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="quick",
        model_ref="gpt-5.4-nano",
        display_name="Nano",
        is_tier_default=True,
    )
    db_session.commit()

    json_body = (
        '{"items":['
        '{"id":"p1","classification":"bullish","confidence":0.9,"key_phrases":["great"]},'
        '{"id":"p2","classification":"bearish","confidence":0.7,"key_phrases":["bad"]}'
        "]}"
    )

    calls: list[object] = []

    async def _fake_generate(self, request):
        calls.append(request)
        return LLMResponse(
            text=json_body,
            finish_reason="stop",
            input_tokens=10,
            output_tokens=20,
        )

    classifier = RefreshingSyncLlmClassifier(db_session_factory=db_session_factory)

    from openlia.llm.adapters.openai import OpenAIAdapter

    with patch.object(OpenAIAdapter, "generate", _fake_generate):
        result = classifier.classify_batch(
            ticker="AAPL",
            posts=[_post("p1", "great quarter"), _post("p2", "meh outlook")],
        )

    labels = [item.classification.value for item in result.items]
    assert calls, "OpenAIAdapter.generate was not invoked"
    assert result.audits, "no audit emitted"
    assert result.audits[0].error is None, f"classifier error: {result.audits[0].error}"
    assert labels == ["bullish", "bearish"]
    assert len(result.audits) == 1
    audit = result.audits[0]
    assert audit.model_ref == "gpt-5.4-nano"
    assert audit.error is None


def test_refreshing_classifier_provider_exception_falls_back_to_neutral(
    _env_secret, db_session, db_session_factory, create_tables
) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="quick",
        model_ref="gpt-5.4-nano",
        display_name="Nano",
        is_tier_default=True,
    )
    db_session.commit()

    async def _boom_generate(self, request):
        raise RuntimeError("provider down")

    classifier = RefreshingSyncLlmClassifier(db_session_factory=db_session_factory)

    from openlia.llm.adapters.openai import OpenAIAdapter

    with patch.object(OpenAIAdapter, "generate", _boom_generate):
        result = classifier.classify_batch(
            ticker="AAPL",
            posts=[_post("p1", "great quarter"), _post("p2", "meh outlook")],
        )

    # LlmClassifier retries once; on second failure falls back to neutral
    # but emits one audit row with the error captured.
    assert [item.classification.value for item in result.items] == ["neutral", "neutral"]
    assert len(result.audits) == 1
    assert "RuntimeError" in (result.audits[0].error or "")


def test_app_factory_installs_refreshing_classifier_on_rs_runner() -> None:
    with patch.dict(
        os.environ,
        {"OPENLIA_DB_URL": "sqlite:///:memory:", "OPENLIA_SCHEDULER_ENABLED": "0"},
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            runner = app.state.rs_runner
            classifier = runner._classifier
            assert isinstance(classifier, RefreshingSyncLlmClassifier)
            assert app.state.rs_classifier is classifier
