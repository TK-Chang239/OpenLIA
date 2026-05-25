"""Verify the openlia / openlia_server loggers emit INFO once create_app runs.

Background: uvicorn's default logging config only attaches handlers to its
own ``uvicorn.*`` loggers. Application loggers fall through to Python's
lastResort handler (stderr, WARNING+), which silently drops INFO. Without
the ``_configure_app_logging`` step the ``llm_usage`` telemetry from
``v2_stage_factory`` never reaches the log even though the code calls
``log.info(...)``. These tests pin both the emission behaviour and the
idempotency contract for repeated ``create_app()`` calls (tests do this).
"""

from __future__ import annotations

import io
import logging

from openlia_server.app import _configure_app_logging


def _reset_logger(name: str) -> None:
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        if getattr(handler, "_openlia_app", False):
            logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


def test_configure_app_logging_emits_info_on_openlia_namespaces() -> None:
    _reset_logger("openlia")
    _reset_logger("openlia_server")
    _configure_app_logging()

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    logging.getLogger("openlia").addHandler(handler)
    logging.getLogger("openlia_server").addHandler(handler)
    try:
        logging.getLogger("openlia.subsystem").info("hello-openlia")
        logging.getLogger("openlia_server.services.x").info("hello-server")
    finally:
        logging.getLogger("openlia").removeHandler(handler)
        logging.getLogger("openlia_server").removeHandler(handler)

    output = buf.getvalue()
    assert "hello-openlia" in output
    assert "hello-server" in output


def test_configure_app_logging_is_idempotent() -> None:
    _reset_logger("openlia")
    _reset_logger("openlia_server")

    _configure_app_logging()
    _configure_app_logging()
    _configure_app_logging()

    for name in ("openlia", "openlia_server"):
        logger = logging.getLogger(name)
        tagged = [h for h in logger.handlers if getattr(h, "_openlia_app", False)]
        assert len(tagged) == 1


def test_configure_app_logging_does_not_promote_third_party_loggers() -> None:
    _reset_logger("openlia")
    _reset_logger("openlia_server")
    third_party = logging.getLogger("some_third_party_lib_for_test")
    third_party.handlers = []
    third_party.setLevel(logging.NOTSET)

    _configure_app_logging()

    assert not any(getattr(h, "_openlia_app", False) for h in third_party.handlers)
