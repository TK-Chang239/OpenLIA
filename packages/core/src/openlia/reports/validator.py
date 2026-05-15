from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from openlia.reports.schema import ReportSchema


class ReportValidationError(ValueError):
    def __init__(self, errors: list[tuple[str, str]]) -> None:
        self.errors = errors
        summary = "; ".join(f"{p}: {m}" for p, m in errors[:5])
        super().__init__(f"Report payload failed validation: {summary}")


def validate_report_payload(payload: dict[str, Any]) -> ReportSchema:
    try:
        return ReportSchema.model_validate(payload)
    except ValidationError as exc:
        collected: list[tuple[str, str]] = []
        for err in exc.errors():
            path = ".".join(str(loc) for loc in err["loc"])
            collected.append((path, err["msg"]))
        raise ReportValidationError(collected) from exc
