from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from openlia.reports.schema import (
    KeyFindingBlock,
    MetricCardsBlock,
    PullQuoteBlock,
    QuoteBlock,
    ReportSchema,
)


@dataclass(frozen=True)
class ReportValidationWarning:
    """Non-fatal validator finding. Phase 5d warns; Phase 6 may promote
    selected kinds to errors via a strict-mode toggle."""

    kind: str
    slot: str
    path: str
    message: str


def find_uncited_concrete_claims(schema: ReportSchema) -> list[ReportValidationWarning]:
    """Walk every value-bearing slot (Metric, KeyFinding, PullQuote,
    Quote) and emit one warning per slot with an empty ``source_ids``.

    The two-source-discipline prompt instructs the model to cite every
    concrete claim; this validator enforces it post-hoc so devs see
    drift before users do. Reports still ship — see ReportRunner for
    how the warnings surface as traces.
    """
    warnings: list[ReportValidationWarning] = []
    for section in schema.sections:
        for block_idx, block in enumerate(section.blocks):
            base = f"sections[{section.id}].blocks[{block_idx}]"
            if isinstance(block, MetricCardsBlock):
                for m_idx, metric in enumerate(block.metrics):
                    if not metric.source_ids:
                        warnings.append(
                            ReportValidationWarning(
                                kind="uncited_concrete_claim",
                                slot="metric",
                                path=f"{base}.metrics[{m_idx}]",
                                message=(
                                    f"Metric '{metric.label}' ({metric.value}) has no source_ids."
                                ),
                            )
                        )
            elif isinstance(block, KeyFindingBlock) and not block.source_ids:
                warnings.append(
                    ReportValidationWarning(
                        kind="uncited_concrete_claim",
                        slot="key_finding",
                        path=base,
                        message="Key finding has no source_ids.",
                    )
                )
            elif isinstance(block, PullQuoteBlock) and not block.source_ids:
                warnings.append(
                    ReportValidationWarning(
                        kind="uncited_concrete_claim",
                        slot="pull_quote",
                        path=base,
                        message="Pull quote has no source_ids.",
                    )
                )
            elif isinstance(block, QuoteBlock) and not block.source_ids:
                warnings.append(
                    ReportValidationWarning(
                        kind="uncited_concrete_claim",
                        slot="quote",
                        path=base,
                        message="Quote has no source_ids.",
                    )
                )
    return warnings


def enforce_required_rail(
    schema: ReportSchema,
    *,
    department_id: str,
    required_labels: tuple[str, ...] | list[str] | None = None,
) -> None:
    """Enforce that single-stock and earnings-update reports populate the
    right-rail "Lia's Call" verdict and a known floor of quick_stats
    labels. Failures raise ``ReportValidationError`` so the writing
    loop's repair turn fires.

    ``required_labels`` is provided by the caller from the template's
    ``rail.required_quick_stats`` list. If ``None`` (not declared by the
    template), rail validation is skipped entirely.

    Quick-stats matching is case-insensitive on the label.
    """
    if required_labels is None:
        return
    errors: list[tuple[str, str]] = []
    details: list[dict[str, Any]] = []
    rail = schema.rail
    if rail is None or rail.verdict is None or not rail.verdict.rating.strip():
        errors.append(
            (
                "rail.verdict",
                "required_rail: rail.verdict.rating is required for this report type.",
            )
        )
        details.append(
            {
                "path": "rail.verdict",
                "message": ("required_rail: rail.verdict.rating is required for this report type."),
                "input_value": "",
                "input_type": "verdict",
            }
        )
    quick_stats = rail.quick_stats if rail is not None else []
    present = {m.label.strip().casefold() for m in quick_stats}
    missing = [label for label in required_labels if label.casefold() not in present]
    for label in missing:
        msg = f"required_rail: rail.quick_stats is missing required label {label!r}."
        errors.append(("rail.quick_stats", msg))
        details.append(
            {
                "path": "rail.quick_stats",
                "message": msg,
                "input_value": "",
                "input_type": "quick_stats",
            }
        )
    if errors:
        raise ReportValidationError(errors, details=details)


def enforce_uncited_concrete_claims(schema: ReportSchema, *, strict: bool) -> None:
    """Phase 6a strict-mode wrapper around ``find_uncited_concrete_claims``.

    - ``strict=False`` (default warn-mode): returns silently. Callers
      still invoke ``find_uncited_concrete_claims`` directly to surface
      warnings as traces.
    - ``strict=True``: any uncited concrete claim becomes a fatal
      ``ReportValidationError`` so the runner's existing rescue/retry
      loop fires. The error mirrors the warnings as ``(path, message)``
      tuples and populates ``details`` in the same shape used by schema
      errors, so trace rendering is identical.
    """
    if not strict:
        return
    warnings = find_uncited_concrete_claims(schema)
    if not warnings:
        return
    errors = [(w.path, f"{w.kind}: {w.message}") for w in warnings]
    details = [
        {
            "path": w.path,
            "message": f"{w.kind}: {w.message}",
            "input_value": "",
            "input_type": w.slot,
        }
        for w in warnings
    ]
    raise ReportValidationError(errors, details=details)


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
        self.details = (
            details
            if details is not None
            else [
                {"path": p, "message": m, "input_value": "", "input_type": "unknown"}
                for p, m in errors
            ]
        )
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
