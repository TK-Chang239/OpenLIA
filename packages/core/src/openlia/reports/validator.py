from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from openlia.reports.schema import ReportSchema


def _repr_truncated(v: Any, *, max_len: int = 120) -> str:
    """Repr the offending input value, bounded so traces stay readable when
    the LLM dropped a 60-element points array into the wrong slot."""
    s = repr(v)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


class ReportValidationError(ValueError):
    def __init__(
        self,
        errors: list[tuple[str, str]],
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.errors = errors
        self.details = details if details is not None else [
            {"path": p, "message": m, "input_value": "", "input_type": "unknown"}
            for p, m in errors
        ]
        summary = "; ".join(f"{p}: {m}" for p, m in errors[:5])
        super().__init__(f"Report payload failed validation: {summary}")


def validate_report_payload(payload: dict[str, Any]) -> ReportSchema:
    try:
        return ReportSchema.model_validate(payload)
    except ValidationError as exc:
        collected: list[tuple[str, str]] = []
        details: list[dict[str, Any]] = []
        for err in exc.errors():
            path = ".".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            collected.append((path, msg))
            raw_input = err.get("input")
            details.append(
                {
                    "path": path,
                    "message": msg,
                    "input_value": _repr_truncated(raw_input),
                    "input_type": type(raw_input).__name__,
                }
            )
        raise ReportValidationError(collected, details=details) from exc
