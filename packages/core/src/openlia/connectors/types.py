"""Pure value types for connector subsystem (v2 redesign).

See docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md
sections §3.1, §6.1, §6.4, §6.5.

This module MUST stay free of FastAPI, SQLAlchemy, and HTTP clients.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Category(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"


class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"
    PYTHON_LIB = "python_lib"
    SKILL = "skill"  # reserved for Layer 2


class ConnectorStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"


@dataclass(frozen=True)
class CliMcpMode:
    kind: Literal["cli_mcp"]
    argv: list[str]
    env_keys: list[str]


@dataclass(frozen=True)
class RemoteMcpMode:
    kind: Literal["remote_mcp"]
    url: str
    headers: dict[str, str]


@dataclass(frozen=True)
class InstanceFactory:
    cls: str
    args: dict[str, Any]  # values may be `$ENV_VAR_NAME` or `${ENV_VAR_NAME}` placeholders


@dataclass(frozen=True)
class PythonLibMode:
    kind: Literal["python_lib"]
    pip_name: str
    pip_version: str
    import_module: str
    instance_factory: InstanceFactory


LaunchMode = CliMcpMode | RemoteMcpMode | PythonLibMode


@dataclass(frozen=True)
class LaunchSpec:
    """Multi-mode launch spec persisted as JSON on Connector.launch.

    A single connector row may expose more than one runtime mode
    (e.g. eodhd as both `cli_mcp` and `python_lib`). The wizard-time
    adapter LLM picks one mode per RunnerNeed when authoring CallableSpecs.
    """

    modes: list[LaunchMode]


@dataclass(frozen=True)
class ToolDefinition:
    """Single tool as returned by `list_tools()` from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class CallableDefinition:
    """Single callable surfaced by a python_lib connector."""

    qualname: str  # e.g. "APIClient.real_time_quote"
    signature: str  # "(symbol: str) -> dict"
    doc: str


@dataclass(frozen=True)
class NeedParameter:
    name: str
    description: str
    type: str
    required: bool
    default: Any = None


@dataclass(frozen=True)
class RunnerNeed:
    """Department-declared data need, resolved at wizard time."""

    id: str
    description: str
    parameters: list[NeedParameter]
    shape: str  # type hint string, e.g. "float", "list[dict]"


@dataclass(frozen=True)
class ParamBinding:
    to_arg: str
    transform: str | None = None  # named entry in TRANSFORMS, or None


@dataclass(frozen=True)
class CallableSpec:
    """Persisted resolution from a RunnerNeed to a concrete connector callable."""

    need_id: str
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"]
    # MCP fields:
    tool_name: str | None = None
    # python_lib fields:
    module: str | None = None
    instance_factory: InstanceFactory | None = None
    method: str | None = None
    # shared fields:
    param_bindings: dict[str, ParamBinding] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    shape: str = "any"
    result_path: tuple[str, ...] = ()
    # Optional reduction applied to the raw transport result BEFORE
    # `result_path` is walked. Useful for upstream APIs that return a
    # time-series list[dict] when the runner expects a single float
    # (e.g. FMP's economics-indicators returns daily/quarterly records).
    # See `RESULT_REDUCERS` for valid names.
    result_reducer: str | None = None


# ISO 3166-1 alpha-2 → alpha-3 for the economies covered by the day-1 catalog.
# EODHD's macro indicators API expects alpha-3 (e.g. USA, DEU, FRA).
_COUNTRY_ISO2_TO_ISO3: dict[str, str] = {
    "US": "USA",
    "GB": "GBR",
    "DE": "DEU",
    "FR": "FRA",
    "JP": "JPN",
    "CN": "CHN",
    "IN": "IND",
    "BR": "BRA",
    "CA": "CAN",
    "AU": "AUS",
    "IT": "ITA",
    "ES": "ESP",
    "NL": "NLD",
    "CH": "CHE",
    "SE": "SWE",
    "NO": "NOR",
    "DK": "DNK",
    "MX": "MEX",
    "KR": "KOR",
    "RU": "RUS",
    "ZA": "ZAF",
    "TR": "TUR",
    "ID": "IDN",
    "SA": "SAU",
    "AR": "ARG",
}


def _country_iso2_to_iso3(code: str) -> str:
    code = code.upper()
    return _COUNTRY_ISO2_TO_ISO3.get(code, code)


TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "upper": str.upper,
    "lower": str.lower,
    "country_iso2_to_iso3": _country_iso2_to_iso3,
}

ALLOWED_TRANSFORMS: frozenset[str] = frozenset(TRANSFORMS.keys())


def _latest_value_by_date(records: Any) -> float:
    """For `[{date, value}, ...]`, pick the latest record by `date` and
    return its `value` as a float. Used by FMP economics-indicators
    specs (e.g. inflationRate) that return a time-series but where the
    runner expects a single float.
    """
    if not isinstance(records, list) or not records:
        raise ValueError(
            f"latest_value_by_date: expected non-empty list, got {type(records).__name__}",
        )
    sorted_records = sorted(records, key=lambda r: r.get("date") or "", reverse=True)
    head = sorted_records[0]
    val = head.get("value")
    if val is None:
        raise ValueError("latest_value_by_date: latest record has no 'value' field")
    return float(val)


def _yoy_pct_quarterly(records: Any) -> float:
    """For `[{date, value}, ...]` of quarterly levels, return year-over-
    year percent change as a float: (latest - 4_quarters_back) /
    4_quarters_back * 100. Used by FMP realGDP spec where the API
    returns levels and the runner expects a YoY %.
    """
    if not isinstance(records, list) or len(records) < 5:
        raise ValueError(
            f"yoy_pct_quarterly: need at least 5 quarterly records to compute YoY, "
            f"got {len(records) if isinstance(records, list) else type(records).__name__}",
        )
    sorted_records = sorted(records, key=lambda r: r.get("date") or "", reverse=True)
    latest = float(sorted_records[0]["value"])
    four_back = float(sorted_records[4]["value"])
    if four_back == 0:
        raise ValueError("yoy_pct_quarterly: 4-quarters-back value is zero, cannot compute YoY %")
    return (latest - four_back) / four_back * 100.0


RESULT_REDUCERS: dict[str, Callable[[Any], Any]] = {
    "latest_value_by_date": _latest_value_by_date,
    "yoy_pct_quarterly": _yoy_pct_quarterly,
}

ALLOWED_RESULT_REDUCERS: frozenset[str] = frozenset(RESULT_REDUCERS.keys())
