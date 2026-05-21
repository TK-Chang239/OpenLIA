from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class HelperParam(BaseModel):
    type: str
    default: Any | None = None
    derivation: str | None = None
    description: str
    required: bool = True


class HelperSchema(BaseModel):
    name: str
    description: str
    params: dict[str, HelperParam]


class HelperRegistration(BaseModel):
    # Renamed from `schema` to avoid shadowing pydantic.BaseModel.schema().
    helper_schema: HelperSchema
    execute: Callable[..., Any] = Field(exclude=True)
    available: bool = True
    deferred_category: str | None = None

    model_config = {"arbitrary_types_allowed": True}


_helpers: dict[str, HelperRegistration] = {}


def register_helper(reg: HelperRegistration) -> None:
    name = reg.helper_schema.name
    if name in _helpers:
        raise ValueError(f"helper {name!r} already registered")
    _helpers[name] = reg


def register_library_helper(
    name: str,
    fn: Callable,
    schema: HelperSchema,
    deferred_category: str | None = None,
) -> None:
    register_helper(
        HelperRegistration(
            helper_schema=schema,
            execute=fn,
            available=(deferred_category is None),
            deferred_category=deferred_category,
        )
    )


def get_helper(name: str) -> HelperRegistration:
    if name not in _helpers:
        raise KeyError(f"no helper registered as {name!r}")
    return _helpers[name]


def list_helpers() -> list[HelperRegistration]:
    return list(_helpers.values())


def reset_helpers_for_tests() -> None:
    _helpers.clear()


def register_deferred_categories() -> None:
    """Register not-yet-implemented placeholders for deferred categories."""
    deferred = [
        ("var_calculator", "Value at Risk", "risk_metrics"),
        ("sharpe_ratio", "Sharpe ratio", "risk_metrics"),
        ("portfolio_optimizer", "Portfolio optimization", "portfolio"),
        ("time_series_analyzer", "Time-series decomposition", "time_series"),
        ("monte_carlo", "Monte Carlo simulation", "quant_finance"),
        ("macro_indicator", "Macro indicator pull", "macro"),
        ("equity_screener", "Equity screener", "screener"),
        ("nlp_sentiment", "NLP sentiment", "nlp"),
        ("pdf_extractor", "PDF text extraction", "pdf_parsing"),
        ("factor_exposure", "Factor exposure", "quant_finance"),
        ("stats_inference", "Statistical inference", "stats"),
    ]
    for name, desc, category in deferred:
        if name in _helpers:
            continue

        def _make_raise(n: str, c: str) -> Callable:
            def _execute(**kw: Any) -> Any:
                raise NotImplementedError(f"{n} is in deferred category {c!r}")

            return _execute

        register_library_helper(
            name=name,
            fn=_make_raise(name, category),
            schema=HelperSchema(name=name, description=desc, params={}),
            deferred_category=category,
        )
