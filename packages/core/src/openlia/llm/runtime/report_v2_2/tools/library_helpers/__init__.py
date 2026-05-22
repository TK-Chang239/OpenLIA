"""Helper registry for report_v2_2 library helpers.

Helpers self-register at module import via register_helper().
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from openlia.llm.runtime.report_v2_2.schema import HelperSchema


@dataclass
class RegisteredHelper:
    schema: HelperSchema
    impl: Callable  # type: ignore[type-arg]


_REGISTRY: dict[str, RegisteredHelper] = {}


def register_helper(schema: HelperSchema, impl: Callable) -> None:  # type: ignore[type-arg]
    """Register a helper. Helpers call this at module import.

    Raises ValueError on duplicate name or unknown artifact_type.

    # Signature diverges from report_v2's HelperRegistration-wrapping pattern: v2.2 takes
    # schema + impl unpacked, dropping the now-unused `available`/`deferred_category`
    # workaround fields.
    """
    if schema.directory.name in _REGISTRY:
        raise ValueError(f"Helper {schema.directory.name!r} already registered")

    # Validate all declared artifact types exist in the ArtifactType registry.
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry as art_reg

    for artifact_id in schema.contract.produces_artifacts + schema.contract.consumes_artifacts:
        if art_reg.get(artifact_id) is None:
            raise ValueError(
                f"Helper {schema.directory.name!r} declares artifact_type "
                f"{artifact_id!r} which is not in the ArtifactType registry"
            )

    _REGISTRY[schema.directory.name] = RegisteredHelper(schema=schema, impl=impl)


def list_helpers() -> list[RegisteredHelper]:
    return list(_REGISTRY.values())


def get_helper(name: str) -> RegisteredHelper | None:
    return _REGISTRY.get(name)


def reset_helpers_for_tests() -> None:
    """Clear registry. Use only in test fixtures."""
    _REGISTRY.clear()


# Eagerly import all helper modules so they register themselves at boot.

from . import (  # noqa: E402, F401
    budget_variance,
    business_investment,
    business_quality,
    chart_builder,
    comparables_run,
    cost_of_capital_builder,
    credit,
    dcf_engine,
    dcf_valuation,
    ddm_family,
    eodhd,
    excel_builder,
    expected_total_return,
    financetoolkit,
    football_field_chart,
    forecast_builder,
    forensic,
    fred,
    implied_upside_downside,
    justified_multiples,
    nlp,
    price_target_blender,
    rating_band_assigner,
    ratio_calculator,
    reverse_dcf,
    risk_macro,
    risk_reward_calculator,
    saas_kpi_panel,
    saas_metrics,
    scenario_weighting,
    sensitivity_table,
    sector,
    signals,
    sotp_builder,
    statsmodels_helpers,
    tornado_diagram,
    waterfall_chart,
    workbook_builder,
)
