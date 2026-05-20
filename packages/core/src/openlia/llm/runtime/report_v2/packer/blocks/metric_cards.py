from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import Metric, MetricCardsBlock, Tag


def _normalize_metric(m: dict[str, Any]) -> Metric:
    m = dict(m)
    # Accept "name", "title", or "metric" as alias for "label".
    if "label" not in m:
        for alias in ("name", "title", "metric"):
            if alias in m:
                m["label"] = m.pop(alias)
                break
    # Accept "amount" or "figure" as alias for "value".
    if "value" not in m:
        for alias in ("amount", "figure"):
            if alias in m:
                m["value"] = m.pop(alias)
                break
    # Coerce non-string values to string (model often emits numbers).
    if "value" in m and not isinstance(m["value"], str):
        m["value"] = str(m["value"])
    if "tag" in m and m["tag"] is not None and isinstance(m["tag"], dict):
        m["tag"] = Tag(**m["tag"])
    return Metric(**m)


def _assemble(
    *, data: dict[str, Any], citation_ids: list[int], manifest_resolver
) -> MetricCardsBlock:
    # Tolerate "cards", "items", or "values" as alias for "metrics".
    raw = data.get("metrics")
    if raw is None:
        for alias in ("cards", "items", "values"):
            if alias in data:
                raw = data[alias]
                break
    if raw is None:
        raise KeyError("metrics")
    metrics = [_normalize_metric(m) for m in raw]
    return MetricCardsBlock(type="metric_cards", metrics=metrics)


def _delta_sign(delta: Any) -> int | None:
    """Return -1, 0, +1 from a delta string/number; None if unparseable.

    Accepts ``"+12%"``, ``"-10%"``, ``"-$3.4B"``, ``0.05``, ``-3``, etc. Strips
    surrounding parentheses (``"(10%)"`` is a common accounting-style negative).
    """
    if delta is None:
        return None
    if isinstance(delta, bool):
        return None
    if isinstance(delta, (int, float)):
        if delta > 0:
            return 1
        if delta < 0:
            return -1
        return 0
    if not isinstance(delta, str):
        return None
    raw = delta.strip()
    if not raw:
        return None
    # Accounting parentheses indicate a negative figure.
    negative_parens = raw.startswith("(") and raw.endswith(")")
    inner = raw[1:-1] if negative_parens else raw
    # Find the first numeric character to detect the leading sign.
    sign = 1
    if inner.startswith("-"):
        sign = -1
    elif inner.startswith("+"):
        sign = 1
    else:
        # No explicit sign; look for digits at all.
        if not any(c.isdigit() for c in inner):
            return None
    if negative_parens:
        sign = -1
    # Detect zero.
    digits = "".join(c for c in inner if c.isdigit() or c == ".")
    if digits:
        try:
            magnitude = float(digits)
        except ValueError:
            magnitude = 1.0
        if magnitude == 0:
            return 0
    return sign


_VALID_DIRECTIONS_POS = {"up", "positive", "+", "increase", "pos"}
_VALID_DIRECTIONS_NEG = {"down", "negative", "-", "decrease", "neg"}
_VALID_DIRECTIONS_FLAT = {"flat", "neutral", "none", "0"}


def _validate_shape(block: dict[str, Any]) -> list[str]:
    """delta_direction MUST agree with the sign of the delta value.

    Closes the CRM "sub-10%" bug where a negative delta was tagged as
    ``up`` and rendered red.
    """
    errors: list[str] = []
    raw_metrics = (
        block.get("metrics") or block.get("cards") or block.get("items") or block.get("values")
    )
    if not raw_metrics or not isinstance(raw_metrics, list):
        errors.append("metric_cards: missing 'metrics' list")
        return errors
    for idx, m in enumerate(raw_metrics):
        if not isinstance(m, dict):
            errors.append(f"metric_cards: metric[{idx}] must be a mapping")
            continue
        delta = m.get("delta")
        direction = m.get("delta_direction")
        if delta is None and direction is None:
            continue
        if direction is None:
            # Direction omitted is fine; the renderer will derive it from sign.
            continue
        sign = _delta_sign(delta)
        if sign is None:
            errors.append(
                f"metric_cards: metric[{idx}] has delta_direction={direction!r} but delta "
                f"{delta!r} is unparseable"
            )
            continue
        direction_norm = str(direction).strip().lower()
        if sign > 0 and direction_norm not in _VALID_DIRECTIONS_POS:
            errors.append(
                f"metric_cards: metric[{idx}] delta {delta!r} is positive but "
                f"delta_direction={direction!r}; must agree"
            )
        elif sign < 0 and direction_norm not in _VALID_DIRECTIONS_NEG:
            errors.append(
                f"metric_cards: metric[{idx}] delta {delta!r} is negative but "
                f"delta_direction={direction!r}; must agree"
            )
        elif sign == 0 and direction_norm not in _VALID_DIRECTIONS_FLAT:
            errors.append(
                f"metric_cards: metric[{idx}] delta {delta!r} is zero but "
                f"delta_direction={direction!r}; must agree"
            )
    return errors


register_block(
    "metric_cards",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["metrics"],
        "properties": {"metrics": {"type": "array", "minItems": 1}},
    },
    validate_shape=_validate_shape,
)
