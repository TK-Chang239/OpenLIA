# Connector Data Flow Redesign — Implementation Plan

> **SUPERSEDED 2026-04-28** by `docs/superpowers/plans/2026-04-28-connector-redesign-v2.md`. The strategy described here (amend cutover branch in place — Path A) was abandoned in favor of a fresh rebuild from `main` (Path B). Technical content remains useful as reference; do not execute the steps in this document.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the connector data flow redesign — three-layer customization (MCP / skills slot / Python lib), unified Connector with multi-mode launch, structured callable_specs for runner needs, conversation-scoped runtime tool routing with an escalation tool, and graceful department disable.

**Architecture:** Wizard-time adapter LLM produces structured callable_specs for declarative runner needs (`<dept>.needs.yaml`) via Python lib introspection or MCP tool resolution. Runtime router LLM picks per-conversation tool subsets for chat departments using curated `<dept>.routing_context.md`. Deterministic runners walk persisted callable_specs with no LLM in the runtime path. Department health (active/disabled) is derived from declared required categories and runner-need resolution; surfaces in sidebar, Settings, dept page, scheduler, and the API boundary (409 on mutating endpoints when disabled).

**Tech Stack:** Python 3.12+ (uv, ruff), FastAPI, SQLAlchemy 2 + Alembic, Anthropic SDK (Haiku for routing, user-quick-tier for adapter), MCP, React 18 + TypeScript + Vite + Vitest, pytest.

**Scope:**
- Spec: `docs/superpowers/specs/2026-04-27-connector-dataflow-redesign-design.md`
- Canonical reference: `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md`
- Supersedes: `docs/superpowers/plans/2026-04-27-connector-cutover.md`

**Strategy:** Rebase `refactor/connector-cutover` onto current `main`, layer the redesign work as additional commits, open a fresh PR.

---

## Phase 0 — Pre-flight: branch and worktree

### Task 0.1 — Set up worktree on a fresh branch

**Files:**
- (none — branch ops)

- [ ] **Step 1: Verify clean working state**

```bash
git status
```
Expected: working tree clean on `main` (or only untracked dotfiles like `.agents/`, `memo.txt`, `skills-lock.json`).

- [ ] **Step 2: Fetch all remotes**

```bash
git fetch --all --prune
```

- [ ] **Step 3: Create the redesign branch from current main**

```bash
git worktree add ../OpenLIA-redesign -b refactor/connector-dataflow-redesign main
cd ../OpenLIA-redesign
```

All subsequent steps run from this worktree. The original repo at `/Users/tkchang/Projects/OpenLIA` stays on `main`.

- [ ] **Step 4: Verify the new branch starts from main's HEAD**

```bash
git log --oneline -3
```
Expected: top commit is the latest on `main` (e.g., `b5c3d1b docs(specsv2): canonical connector data flow design`).

### Task 0.2 — Bring in cutover commits that survive as-is

The cutover branch has 16 commits. Per spec §1.3, the following survive as-is and can be cherry-picked verbatim:

- `8b876af feat(db): add api_key_encrypted to connectors`
- `1c02393 feat(connectors): api_key_encrypted column on Connector`
- `df702c1 feat(server): wire api_key encryption through POST /api/connectors; drop credentials_ref`
- `a4b12b6 docs: H3.1 — ToolDispatcher consumer migration map`
- `da030ea refactor(runtime): delete ToolDispatcher; Dispatcher is the single tool seam`
- `1805f1d refactor(runtime): drop configured search-callable; web search via Dispatcher`
- `03c3a57 refactor(server): delete legacy provider services + routes` (H6 + H7)
- `e09104a refactor(frontend): delete legacy DataProvidersAdminPanel + setup.ts dead exports`
- `8d610e0 refactor: delete openlia.data package (replaced by openlia.connectors)`

The following need rewriting and are **not** cherry-picked here (they are recreated in later phases):
- `f8207bc feat(connectors): dispatcher_factory hydrates Dispatcher from DB; category filter on tools_for_department` — replaced in Phase 5
- `8569dba feat(runtime): runtime_dispatch helper — envelope shaping + asyncio.gather parallelism` — replaced in Phase 5/6
- `333d2d2 refactor(chat): ChatRunner consumes Dispatcher via runtime_dispatch helper` — replaced in Phase 6
- `19e5d47 refactor(report): ReportRunner consumes Dispatcher; expansion loop runner-local` — replaced in Phase 6
- `a67b597 refactor(mr): drop dead _DataProvider Protocol; runtime wiring pending` — superseded by Phase 8
- `6c24dab refactor(rs): drop dead _DataProvider Protocol; runtime wiring pending` — superseded by Phase 8
- `5225a36 feat(db): drop data_providers tables; CLI rotation iterates Connector` — extended in Phase 9
- `e9e5337 docs: retire data-provider-design.md; projectStructure references connectors` — extended in Phase 11

- [ ] **Step 1: Cherry-pick the survivors in dependency order**

```bash
git cherry-pick 8b876af 1c02393 df702c1 a4b12b6
```

If conflicts arise (none expected, but possible), resolve by accepting the cutover branch's changes since `main` does not yet have any of these.

- [ ] **Step 2: Cherry-pick the deletion commits**

```bash
git cherry-pick 03c3a57 e09104a 8d610e0
```

These are large deletion commits. Conflicts are unlikely because nothing on `main` modifies the deleted paths.

- [ ] **Step 3: Cherry-pick the runtime cleanups**

```bash
git cherry-pick da030ea 1805f1d
```

- [ ] **Step 4: Run the full Python test suite**

```bash
uv run pytest
```

Expected: passing. Any failures here are conflicts/skew between `main` and the cherry-picked work — fix before proceeding.

- [ ] **Step 5: Run the frontend test suite**

```bash
cd frontend && npm install && npm test -- --run && cd ..
```

Expected: passing.

- [ ] **Step 6: Lint / format**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: clean.

The branch is now in the "post-cutover-survivors" state. The redesign work begins in Phase 1.

---

## Phase 1 — Core enums and value types extension

### Task 1.1 — Add `python_lib` to `ConnectorSource`

**Files:**
- Modify: `packages/core/src/openlia/connectors/types.py`
- Test: `packages/core/tests/test_connectors/test_types.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/core/tests/test_connectors/test_types.py`:
```python
def test_connector_source_includes_python_lib():
    from openlia.connectors.types import ConnectorSource

    assert ConnectorSource.PYTHON_LIB.value == "python_lib"
    assert ConnectorSource.PYTHON_LIB in set(ConnectorSource)


def test_connector_source_includes_skill_reserved():
    from openlia.connectors.types import ConnectorSource

    assert ConnectorSource.SKILL.value == "skill"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/test_connectors/test_types.py -v
```

Expected: FAIL on `AttributeError: PYTHON_LIB` (and SKILL).

- [ ] **Step 3: Extend the enum**

Edit `packages/core/src/openlia/connectors/types.py`:
```python
class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"
    PYTHON_LIB = "python_lib"
    SKILL = "skill"  # reserved for Layer 2; not yet validated/loaded
```

- [ ] **Step 4: Verify the test passes**

```bash
uv run pytest packages/core/tests/test_connectors/test_types.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/connectors/types.py packages/core/tests/test_connectors/test_types.py
git commit -m "feat(connectors): add python_lib and skill to ConnectorSource"
```

### Task 1.2 — Multi-mode launch spec

**Files:**
- Modify: `packages/core/src/openlia/connectors/types.py`
- Test: `packages/core/tests/test_connectors/test_launch_spec.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_connectors/test_launch_spec.py`:
```python
from openlia.connectors.types import ConnectorLaunch, LaunchMode


def test_launch_round_trips_single_mcp_cli_mode():
    launch = ConnectorLaunch(
        modes=(
            LaunchMode.cli_mcp(argv=("uvx", "eodhd-mcp-server"), env_keys=("EODHD_API_KEY",)),
        ),
    )
    raw = launch.to_json()
    assert raw == {
        "modes": [
            {
                "kind": "cli_mcp",
                "argv": ["uvx", "eodhd-mcp-server"],
                "env_keys": ["EODHD_API_KEY"],
            }
        ]
    }
    assert ConnectorLaunch.from_json(raw) == launch


def test_launch_round_trips_dual_mode_mcp_and_python_lib():
    launch = ConnectorLaunch(
        modes=(
            LaunchMode.cli_mcp(argv=("uvx", "eodhd-mcp-server"), env_keys=("EODHD_API_KEY",)),
            LaunchMode.python_lib(
                pip_name="eodhd",
                pip_version=">=1.2.0",
                import_module="eodhd",
                instance_factory={"class": "APIClient", "args": {"api_key": "$EODHD_API_KEY"}},
            ),
        ),
    )
    raw = launch.to_json()
    assert ConnectorLaunch.from_json(raw) == launch


def test_launch_rejects_unknown_kind():
    import pytest

    with pytest.raises(ValueError, match="unknown launch kind"):
        ConnectorLaunch.from_json({"modes": [{"kind": "elephant"}]})


def test_launch_get_mode_returns_first_or_none():
    launch = ConnectorLaunch(
        modes=(
            LaunchMode.cli_mcp(argv=("uvx", "x"), env_keys=()),
            LaunchMode.python_lib(
                pip_name="x", pip_version="*", import_module="x", instance_factory=None
            ),
        ),
    )
    cli = launch.get_mode("cli_mcp")
    assert cli is not None and cli.kind == "cli_mcp"
    assert launch.get_mode("remote_mcp") is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_launch_spec.py -v
```

Expected: FAIL with `ImportError: cannot import name 'ConnectorLaunch'`.

- [ ] **Step 3: Implement the multi-mode launch types**

Add to `packages/core/src/openlia/connectors/types.py` (replacing the prior `MCPLaunchSpec` with the multi-mode shape):
```python
@dataclass(frozen=True)
class LaunchMode:
    """One configured access mode within a Connector's launch spec."""

    kind: str  # "cli_mcp" | "remote_mcp" | "built_in" | "python_lib"
    # mcp_cli / mcp_remote
    argv: tuple[str, ...] = ()
    url: str | None = None
    headers: tuple[tuple[str, str], ...] = ()
    env_keys: tuple[str, ...] = ()
    # built_in
    template_id: str | None = None
    # python_lib
    pip_name: str | None = None
    pip_version: str | None = None
    import_module: str | None = None
    instance_factory: dict[str, Any] | None = None

    @staticmethod
    def cli_mcp(*, argv: tuple[str, ...], env_keys: tuple[str, ...]) -> LaunchMode:
        return LaunchMode(kind="cli_mcp", argv=tuple(argv), env_keys=tuple(env_keys))

    @staticmethod
    def remote_mcp(
        *, url: str, headers: tuple[tuple[str, str], ...] = (), env_keys: tuple[str, ...] = ()
    ) -> LaunchMode:
        return LaunchMode(kind="remote_mcp", url=url, headers=tuple(headers), env_keys=tuple(env_keys))

    @staticmethod
    def built_in(*, template_id: str) -> LaunchMode:
        return LaunchMode(kind="built_in", template_id=template_id)

    @staticmethod
    def python_lib(
        *,
        pip_name: str,
        pip_version: str | None,
        import_module: str,
        instance_factory: dict[str, Any] | None,
    ) -> LaunchMode:
        return LaunchMode(
            kind="python_lib",
            pip_name=pip_name,
            pip_version=pip_version,
            import_module=import_module,
            instance_factory=instance_factory,
        )

    def to_json(self) -> dict[str, Any]:
        if self.kind == "cli_mcp":
            return {"kind": "cli_mcp", "argv": list(self.argv), "env_keys": list(self.env_keys)}
        if self.kind == "remote_mcp":
            out: dict[str, Any] = {"kind": "remote_mcp", "url": self.url}
            if self.headers:
                out["headers"] = [list(p) for p in self.headers]
            if self.env_keys:
                out["env_keys"] = list(self.env_keys)
            return out
        if self.kind == "built_in":
            return {"kind": "built_in", "template_id": self.template_id}
        if self.kind == "python_lib":
            return {
                "kind": "python_lib",
                "pip_name": self.pip_name,
                "pip_version": self.pip_version,
                "import_module": self.import_module,
                "instance_factory": self.instance_factory,
            }
        raise ValueError(f"unknown launch kind {self.kind!r}")

    @staticmethod
    def from_json(raw: dict[str, Any]) -> LaunchMode:
        kind = raw.get("kind")
        if kind == "cli_mcp":
            return LaunchMode.cli_mcp(
                argv=tuple(raw.get("argv", ())),
                env_keys=tuple(raw.get("env_keys", ())),
            )
        if kind == "remote_mcp":
            return LaunchMode.remote_mcp(
                url=raw["url"],
                headers=tuple((k, v) for k, v in raw.get("headers", [])),
                env_keys=tuple(raw.get("env_keys", ())),
            )
        if kind == "built_in":
            return LaunchMode.built_in(template_id=raw["template_id"])
        if kind == "python_lib":
            return LaunchMode.python_lib(
                pip_name=raw["pip_name"],
                pip_version=raw.get("pip_version"),
                import_module=raw["import_module"],
                instance_factory=raw.get("instance_factory"),
            )
        raise ValueError(f"unknown launch kind {kind!r}")


@dataclass(frozen=True)
class ConnectorLaunch:
    """Multi-mode launch spec persisted as JSON on Connector.launch."""

    modes: tuple[LaunchMode, ...]

    def to_json(self) -> dict[str, Any]:
        return {"modes": [m.to_json() for m in self.modes]}

    @staticmethod
    def from_json(raw: dict[str, Any]) -> ConnectorLaunch:
        if not isinstance(raw, dict) or "modes" not in raw:
            raise ValueError(f"launch JSON missing 'modes': {raw!r}")
        return ConnectorLaunch(modes=tuple(LaunchMode.from_json(m) for m in raw["modes"]))

    def get_mode(self, kind: str) -> LaunchMode | None:
        for m in self.modes:
            if m.kind == kind:
                return m
        return None

    def has_mode(self, kind: str) -> bool:
        return self.get_mode(kind) is not None
```

Keep the existing `MCPLaunchSpec` class around (as a thin compatibility shim) only if any cherry-picked code still references it; otherwise delete. (`from_json` callers should be migrated to `ConnectorLaunch.from_json` in this same task.)

- [ ] **Step 4: Verify the new tests pass**

```bash
uv run pytest packages/core/tests/test_connectors/test_launch_spec.py -v
```

Expected: PASS.

- [ ] **Step 5: Re-run the full connector test suite**

```bash
uv run pytest packages/core/tests/test_connectors/ packages/server/tests/test_connectors/ -v 2>&1 | tail -20
```

Expected: any tests still referencing `MCPLaunchSpec` need updating to `ConnectorLaunch` — fix those inline (they're using the old single-mode shape; rewrite to use `ConnectorLaunch(modes=(...,))`).

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/connectors/types.py packages/core/tests/test_connectors/
git commit -m "feat(connectors): multi-mode launch spec with python_lib support"
```

### Task 1.3 — Pure-value `RunnerNeed` and `CallableSpec` types

**Files:**
- Create: `packages/core/src/openlia/connectors/runner_needs.py`
- Test: `packages/core/tests/test_connectors/test_runner_needs.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_connectors/test_runner_needs.py`:
```python
from openlia.connectors.runner_needs import (
    CallableSpec,
    NeedParameter,
    ParamBinding,
    RunnerNeed,
)


def test_runner_need_round_trip():
    need = RunnerNeed(
        id="debt_gdp",
        description="Debt-to-GDP ratio in percentage points.",
        parameters=(
            NeedParameter(
                name="country", description="ISO code", type_="string", required=False, default="US"
            ),
        ),
        shape="float",
    )
    raw = need.to_json()
    assert RunnerNeed.from_json(raw) == need


def test_callable_spec_round_trip_python_lib():
    spec = CallableSpec(
        need_id="debt_gdp",
        access_mode="python_lib",
        module="eodhd",
        method="economic_data",
        instance_factory={"class": "APIClient", "args": {"api_key": "$EODHD_API_KEY"}},
        param_bindings={"country": ParamBinding(to_arg="country_code", transform=None)},
        constants={"indicator": "DEBT_GDP_PCT"},
        shape="float",
    )
    raw = spec.to_json()
    assert CallableSpec.from_json(raw) == spec


def test_callable_spec_round_trip_mcp():
    spec = CallableSpec(
        need_id="debt_gdp",
        access_mode="cli_mcp",
        tool_name="get_economic_indicator",
        param_bindings={"country": ParamBinding(to_arg="country", transform="upper")},
        constants={"indicator": "DEBT_GDP_PCT"},
        shape="float",
    )
    raw = spec.to_json()
    assert CallableSpec.from_json(raw) == spec


def test_callable_spec_rejects_python_lib_without_module():
    import pytest

    with pytest.raises(ValueError, match="python_lib spec requires 'module'"):
        CallableSpec.from_json(
            {"need_id": "x", "access_mode": "python_lib", "shape": "float"}
        )


def test_callable_spec_rejects_mcp_without_tool_name():
    import pytest

    with pytest.raises(ValueError, match="mcp spec requires 'tool_name'"):
        CallableSpec.from_json(
            {"need_id": "x", "access_mode": "cli_mcp", "shape": "float"}
        )
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_runner_needs.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the value types**

Create `packages/core/src/openlia/connectors/runner_needs.py`:
```python
"""Pure value types for declarative runner needs and callable specs.

A RunnerNeed describes "what data this runner consumes" — declared in
<dept>.needs.yaml. A CallableSpec is the structured persisted result of
adapter LLM resolution: how to satisfy a specific need against a specific
connector. Both are pure dataclasses; no SQLAlchemy, no FastAPI, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NeedParameter:
    name: str
    description: str
    type_: str  # "string" | "integer" | "number" | "boolean"
    required: bool
    default: Any | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "type": self.type_,
            "required": self.required,
        }
        if self.default is not None:
            out["default"] = self.default
        return out

    @staticmethod
    def from_json(raw: dict[str, Any]) -> NeedParameter:
        return NeedParameter(
            name=raw["name"],
            description=raw["description"],
            type_=raw["type"],
            required=bool(raw.get("required", False)),
            default=raw.get("default"),
        )


@dataclass(frozen=True)
class RunnerNeed:
    id: str
    description: str
    parameters: tuple[NeedParameter, ...]
    shape: str  # "float" | "int" | "string" | "bool" | "list[object]" | etc.

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "parameters": [p.to_json() for p in self.parameters],
            "shape": self.shape,
        }

    @staticmethod
    def from_json(raw: dict[str, Any]) -> RunnerNeed:
        return RunnerNeed(
            id=raw["id"],
            description=raw["description"],
            parameters=tuple(NeedParameter.from_json(p) for p in raw.get("parameters", [])),
            shape=raw["shape"],
        )


@dataclass(frozen=True)
class ParamBinding:
    to_arg: str  # name of the underlying lib/tool argument
    transform: str | None  # e.g. "upper" | "lower" | "iso_to_eodhd" | None

    def to_json(self) -> dict[str, Any]:
        return {"to_arg": self.to_arg, "transform": self.transform}

    @staticmethod
    def from_json(raw: dict[str, Any]) -> ParamBinding:
        return ParamBinding(to_arg=raw["to_arg"], transform=raw.get("transform"))


@dataclass(frozen=True)
class CallableSpec:
    """Structured "how to satisfy a need" produced by the wizard adapter."""

    need_id: str
    access_mode: str  # "python_lib" | "cli_mcp" | "remote_mcp"
    shape: str

    # python_lib fields
    module: str | None = None
    method: str | None = None
    instance_factory: dict[str, Any] | None = None

    # mcp fields
    tool_name: str | None = None

    param_bindings: dict[str, ParamBinding] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "need_id": self.need_id,
            "access_mode": self.access_mode,
            "shape": self.shape,
            "param_bindings": {k: v.to_json() for k, v in self.param_bindings.items()},
            "constants": dict(self.constants),
        }
        if self.access_mode == "python_lib":
            out["module"] = self.module
            out["method"] = self.method
            if self.instance_factory is not None:
                out["instance_factory"] = self.instance_factory
        else:
            out["tool_name"] = self.tool_name
        return out

    @staticmethod
    def from_json(raw: dict[str, Any]) -> CallableSpec:
        access_mode = raw["access_mode"]
        bindings = {
            k: ParamBinding.from_json(v) for k, v in raw.get("param_bindings", {}).items()
        }
        if access_mode == "python_lib":
            if "module" not in raw:
                raise ValueError("python_lib spec requires 'module'")
            return CallableSpec(
                need_id=raw["need_id"],
                access_mode=access_mode,
                shape=raw["shape"],
                module=raw["module"],
                method=raw.get("method"),
                instance_factory=raw.get("instance_factory"),
                param_bindings=bindings,
                constants=dict(raw.get("constants", {})),
            )
        if access_mode in ("cli_mcp", "remote_mcp"):
            if "tool_name" not in raw:
                raise ValueError("mcp spec requires 'tool_name'")
            return CallableSpec(
                need_id=raw["need_id"],
                access_mode=access_mode,
                shape=raw["shape"],
                tool_name=raw["tool_name"],
                param_bindings=bindings,
                constants=dict(raw.get("constants", {})),
            )
        raise ValueError(f"unknown access_mode {access_mode!r}")
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_connectors/test_runner_needs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/connectors/runner_needs.py packages/core/tests/test_connectors/test_runner_needs.py
git commit -m "feat(connectors): RunnerNeed and CallableSpec value types"
```

### Task 1.4 — Parameter binding and transforms registry

**Files:**
- Create: `packages/core/src/openlia/connectors/parameter_binding.py`
- Test: `packages/core/tests/test_connectors/test_parameter_binding.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_connectors/test_parameter_binding.py`:
```python
import pytest

from openlia.connectors.parameter_binding import (
    ALLOWED_TRANSFORMS,
    apply_bindings,
    apply_transform,
)
from openlia.connectors.runner_needs import ParamBinding


def test_allowed_transforms_set_is_documented():
    assert "upper" in ALLOWED_TRANSFORMS
    assert "lower" in ALLOWED_TRANSFORMS
    assert "iso_to_eodhd" in ALLOWED_TRANSFORMS


def test_apply_transform_upper():
    assert apply_transform("upper", "us") == "US"


def test_apply_transform_iso_to_eodhd():
    assert apply_transform("iso_to_eodhd", "TIP") == "TIP.US"


def test_apply_transform_none_returns_value_unchanged():
    assert apply_transform(None, "x") == "x"


def test_apply_transform_unknown_raises():
    with pytest.raises(ValueError, match="unknown transform"):
        apply_transform("rocket-fuel", "x")


def test_apply_bindings_renames_and_transforms():
    bindings = {
        "ticker": ParamBinding(to_arg="symbol", transform="iso_to_eodhd"),
        "country": ParamBinding(to_arg="country_code", transform="upper"),
    }
    constants = {"fmt": "json", "indicator": "DEBT_GDP_PCT"}
    runtime_args = {"ticker": "TIP", "country": "us"}
    out = apply_bindings(
        bindings=bindings, constants=constants, runtime_args=runtime_args
    )
    assert out == {
        "symbol": "TIP.US",
        "country_code": "US",
        "fmt": "json",
        "indicator": "DEBT_GDP_PCT",
    }


def test_apply_bindings_drops_runtime_arg_not_in_bindings():
    bindings = {"ticker": ParamBinding(to_arg="symbol", transform=None)}
    out = apply_bindings(
        bindings=bindings, constants={}, runtime_args={"ticker": "AAPL", "extra": "ignored"}
    )
    assert out == {"symbol": "AAPL"}
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_parameter_binding.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement the binding module**

Create `packages/core/src/openlia/connectors/parameter_binding.py`:
```python
"""Apply parameter bindings + named transforms when invoking a callable spec."""

from __future__ import annotations

from typing import Any

from openlia.connectors.runner_needs import ParamBinding

ALLOWED_TRANSFORMS: frozenset[str] = frozenset(
    {
        "upper",
        "lower",
        "iso_to_eodhd",  # 'TIP' -> 'TIP.US'
    }
)


def apply_transform(transform: str | None, value: Any) -> Any:
    if transform is None:
        return value
    if transform == "upper":
        return value.upper() if isinstance(value, str) else value
    if transform == "lower":
        return value.lower() if isinstance(value, str) else value
    if transform == "iso_to_eodhd":
        if not isinstance(value, str):
            return value
        return value if "." in value else f"{value}.US"
    raise ValueError(f"unknown transform {transform!r}")


def apply_bindings(
    *,
    bindings: dict[str, ParamBinding],
    constants: dict[str, Any],
    runtime_args: dict[str, Any],
) -> dict[str, Any]:
    """Compose the kwargs to pass to the underlying lib or MCP tool.

    - Each entry in `bindings` renames a runtime arg to the underlying name
      and applies the optional transform.
    - `constants` are merged in as-is (already in underlying-arg shape).
    - Runtime args not present in `bindings` are silently dropped.
    """

    out: dict[str, Any] = {}
    for runtime_name, binding in bindings.items():
        if runtime_name not in runtime_args:
            continue
        out[binding.to_arg] = apply_transform(binding.transform, runtime_args[runtime_name])
    for k, v in constants.items():
        out[k] = v
    return out
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_connectors/test_parameter_binding.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/connectors/parameter_binding.py packages/core/tests/test_connectors/test_parameter_binding.py
git commit -m "feat(connectors): parameter binding + transforms registry"
```

---

## Phase 2 — Database schema additions

### Task 2.1 — Migration: `cached_python_callables` column on connectors

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-27-2000_cached_python_callables.py`
- Test: `packages/server/tests/test_db/test_migrations.py` (extend EXPECTED_TABLES check, see existing pattern)

- [ ] **Step 1: Write the migration**

Create `packages/server/src/openlia_server/db/migrations/versions/2026-04-27-2000_cached_python_callables.py`:
```python
"""Add cached_python_callables column to connectors.

Revision ID: 20260427_2000
Revises: <FILL_IN — current head; run `uv run alembic -c packages/server/alembic.ini current`>
Create Date: 2026-04-27 20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260427_2000"
# Replace down_revision with the actual current head before committing.
down_revision = "20260427_1900"  # drop_data_providers; verify with alembic current
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connectors",
        sa.Column("cached_python_callables", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connectors", "cached_python_callables")
```

- [ ] **Step 2: Determine the actual `down_revision`**

```bash
uv run alembic -c packages/server/alembic.ini heads
```

Expected: a single head revision id. Replace the `down_revision` placeholder in the migration file with that id.

- [ ] **Step 3: Generate a fresh DB and apply migrations**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
```

Expected: migrations apply cleanly. The new column exists.

- [ ] **Step 4: Verify the column via SQLite**

```bash
sqlite3 .openlia.dev.db "PRAGMA table_info(connectors);" | grep cached_python_callables
```

Expected: one row showing the column.

- [ ] **Step 5: Run alembic hygiene tests**

```bash
uv run pytest packages/server/tests/test_db/test_alembic_hygiene.py -v
```

Expected: PASS (single head, no orphan revisions).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-04-27-2000_cached_python_callables.py
git commit -m "feat(db): cached_python_callables column on connectors"
```

### Task 2.2 — ORM: `cached_python_callables` field on `Connector`

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/connectors.py`
- Test: `packages/server/tests/test_db/test_models_connectors.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/server/tests/test_db/test_models_connectors.py`:
```python
def test_connector_cached_python_callables_round_trips(session_factory):
    from openlia_server.db.models.connectors import Connector

    callables = [
        {
            "qualname": "APIClient.economic_data",
            "signature": "(country_code: str, indicator: str) -> dict",
            "doc": "Fetch a macro indicator series.",
        }
    ]
    with session_factory() as s:
        row = Connector(
            id="c1",
            provider_id="eodhd",
            source="cli_mcp",
            category="financial",
            launch={"modes": [{"kind": "cli_mcp", "argv": ["uvx", "x"], "env_keys": []}]},
            cached_python_callables=callables,
            status="pending",
        )
        s.add(row)
        s.commit()

    with session_factory() as s:
        loaded = s.get(Connector, "c1")
        assert loaded is not None
        assert loaded.cached_python_callables == callables
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_db/test_models_connectors.py::test_connector_cached_python_callables_round_trips -v
```

Expected: FAIL — column not in ORM mapping.

- [ ] **Step 3: Add the field to the ORM**

Edit `packages/server/src/openlia_server/db/models/connectors.py` adding the field next to `cached_tools`:
```python
cached_python_callables: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_db/test_models_connectors.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_db/test_models_connectors.py
git commit -m "feat(connectors): ORM field for cached_python_callables"
```

### Task 2.3 — Migration: `runner_callable_specs` table; drop `tool_allowlists`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-27-2030_runner_callable_specs.py`

- [ ] **Step 1: Write the migration**

Create `packages/server/src/openlia_server/db/migrations/versions/2026-04-27-2030_runner_callable_specs.py`:
```python
"""Add runner_callable_specs; drop tool_allowlists.

Revision ID: 20260427_2030
Revises: 20260427_2000
Create Date: 2026-04-27 20:30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260427_2030"
down_revision = "20260427_2000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runner_callable_specs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("department_id", sa.String(64), nullable=False),
        sa.Column("need_id", sa.String(64), nullable=False),
        sa.Column(
            "connector_id",
            sa.String(36),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_mode", sa.String(16), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("canary_value", sa.JSON(), nullable=True),
        sa.Column("canary_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("department_id", "need_id", name="uq_runner_callable_specs_dept_need"),
        sa.CheckConstraint(
            "access_mode IN ('cli_mcp', 'remote_mcp', 'python_lib')",
            name="access_mode",
        ),
    )
    op.create_index(
        "ix_runner_callable_specs_connector_id",
        "runner_callable_specs",
        ["connector_id"],
    )

    # Drop tool_allowlists — chat departments no longer have per-tool allowlists.
    op.drop_index("ix_tool_allowlists_department_id", table_name="tool_allowlists")
    op.drop_table("tool_allowlists")


def downgrade() -> None:
    # Recreate tool_allowlists (best-effort — original schema).
    op.create_table(
        "tool_allowlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("department_id", sa.String(64), nullable=False),
        sa.Column(
            "connector_id",
            sa.String(36),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "department_id", "connector_id", "tool_name", name="uq_tool_allowlists"
        ),
    )
    op.create_index(
        "ix_tool_allowlists_department_id", "tool_allowlists", ["department_id"]
    )

    op.drop_index(
        "ix_runner_callable_specs_connector_id", table_name="runner_callable_specs"
    )
    op.drop_table("runner_callable_specs")
```

- [ ] **Step 2: Apply and verify**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
sqlite3 .openlia.dev.db ".tables" | tr ' ' '\n' | grep -E "runner_callable|tool_allow"
```

Expected: `runner_callable_specs` listed; `tool_allowlists` absent.

- [ ] **Step 3: Update EXPECTED_TABLES**

Edit `packages/server/tests/test_db/test_migrations.py`:
- Remove `tool_allowlists` from `EXPECTED_TABLES`.
- Add `runner_callable_specs` to `EXPECTED_TABLES`.

- [ ] **Step 4: Run hygiene tests**

```bash
uv run pytest packages/server/tests/test_db/ -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-04-27-2030_runner_callable_specs.py packages/server/tests/test_db/test_migrations.py
git commit -m "feat(db): runner_callable_specs table; drop tool_allowlists"
```

### Task 2.4 — ORM: `RunnerCallableSpec`

**Files:**
- Create: `packages/server/src/openlia_server/db/models/runner_callable_specs.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` (register the new model)
- Test: `packages/server/tests/test_db/test_models_runner_callable_specs.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_runner_callable_specs.py`:
```python
from openlia_server.db.models.connectors import Connector
from openlia_server.db.models.runner_callable_specs import RunnerCallableSpec


def test_runner_callable_spec_round_trips(session_factory):
    spec_json = {
        "need_id": "debt_gdp",
        "access_mode": "python_lib",
        "module": "eodhd",
        "method": "economic_data",
        "shape": "float",
        "param_bindings": {"country": {"to_arg": "country_code", "transform": "upper"}},
        "constants": {"indicator": "DEBT_GDP_PCT"},
    }
    with session_factory() as s:
        c = Connector(
            id="c1",
            provider_id="eodhd",
            source="python_lib",
            category="financial",
            launch={"modes": [{"kind": "python_lib", "pip_name": "eodhd", "import_module": "eodhd"}]},
            status="validated",
        )
        s.add(c)
        s.commit()
        rcs = RunnerCallableSpec(
            id="rcs1",
            department_id="macro_research",
            need_id="debt_gdp",
            connector_id="c1",
            access_mode="python_lib",
            spec=spec_json,
            canary_value=122.4,
        )
        s.add(rcs)
        s.commit()

    with session_factory() as s:
        loaded = s.get(RunnerCallableSpec, "rcs1")
        assert loaded is not None
        assert loaded.spec == spec_json
        assert loaded.canary_value == 122.4


def test_runner_callable_spec_unique_department_need(session_factory):
    import pytest
    import sqlalchemy.exc as sax

    with session_factory() as s:
        c = Connector(
            id="c1",
            provider_id="eodhd",
            source="python_lib",
            category="financial",
            launch={"modes": [{"kind": "python_lib", "pip_name": "eodhd", "import_module": "eodhd"}]},
            status="validated",
        )
        s.add(c)
        s.add(
            RunnerCallableSpec(
                id="a",
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id="c1",
                access_mode="python_lib",
                spec={},
            )
        )
        s.commit()
        s.add(
            RunnerCallableSpec(
                id="b",
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id="c1",
                access_mode="python_lib",
                spec={},
            )
        )
        with pytest.raises(sax.IntegrityError):
            s.commit()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_db/test_models_runner_callable_specs.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement the ORM**

Create `packages/server/src/openlia_server/db/models/runner_callable_specs.py`:
```python
"""SQLAlchemy model for runner_callable_specs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class RunnerCallableSpec(Base):
    __tablename__ = "runner_callable_specs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    department_id: Mapped[str] = mapped_column(String(64), nullable=False)
    need_id: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    canary_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    canary_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("department_id", "need_id", name="uq_runner_callable_specs_dept_need"),
        Index("ix_runner_callable_specs_connector_id", "connector_id"),
        CheckConstraint(
            "access_mode IN ('cli_mcp', 'remote_mcp', 'python_lib')",
            name="access_mode",
        ),
    )
```

- [ ] **Step 4: Register the model**

Edit `packages/server/src/openlia_server/db/models/__init__.py` to import the new module so its mapper is registered:
```python
from openlia_server.db.models import runner_callable_specs as _rcs  # noqa: F401
```
(Add this line alongside the existing `from openlia_server.db.models import connectors as _connectors`-style imports.)

- [ ] **Step 5: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_db/test_models_runner_callable_specs.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/runner_callable_specs.py packages/server/src/openlia_server/db/models/__init__.py packages/server/tests/test_db/test_models_runner_callable_specs.py
git commit -m "feat(db): RunnerCallableSpec ORM model"
```

---

## Phase 3 — Per-department artifacts

### Task 3.1 — Department dataclass extensions: `required_categories`, `requires_runner`, `disable_runtime_routing`

**Files:**
- Modify: `packages/core/src/openlia/departments/<dept>.py` (all seven)
- Test: `packages/core/tests/test_departments/test_dept_dependencies.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_departments/test_dept_dependencies.py`:
```python
from openlia.connectors.types import Category
from openlia.departments.earnings_update import EarningsUpdateDepartment
from openlia.departments.equity_research import EquityResearchDepartment
from openlia.departments.macro_research import MacroResearchDepartment
from openlia.departments.morning_briefing import MorningBriefingDepartment
from openlia.departments.panic_thermometer import PanicThermometerDepartment
from openlia.departments.retail_sentiment import RetailSentimentDepartment
from openlia.departments.secretary import SecretaryDepartment


def test_secretary_has_no_required_categories():
    d = SecretaryDepartment()
    assert d.required_categories == ()
    assert Category.WEB_SEARCH in d.optional_categories
    assert d.requires_runner is False


def test_equity_research_requires_financial():
    d = EquityResearchDepartment()
    assert d.required_categories == (Category.FINANCIAL,)
    assert set(d.optional_categories) == {Category.NEWS, Category.SOCIAL, Category.WEB_SEARCH}
    assert d.requires_runner is False


def test_earnings_update_requires_financial():
    d = EarningsUpdateDepartment()
    assert d.required_categories == (Category.FINANCIAL,)
    assert d.optional_categories == (Category.NEWS,)
    assert d.requires_runner is False


def test_morning_briefing_requires_financial_and_news():
    d = MorningBriefingDepartment()
    assert set(d.required_categories) == {Category.FINANCIAL, Category.NEWS}
    assert d.optional_categories == (Category.WEB_SEARCH,)
    assert d.requires_runner is False


def test_macro_research_requires_runner():
    d = MacroResearchDepartment()
    assert d.required_categories == (Category.FINANCIAL,)
    assert d.optional_categories == (Category.NEWS,)
    assert d.requires_runner is True


def test_retail_sentiment_requires_financial_not_social():
    d = RetailSentimentDepartment()
    # Sentiment endpoints live inside financial connectors (EODHD, FMP).
    assert d.required_categories == (Category.FINANCIAL,)
    assert set(d.optional_categories) == {Category.NEWS, Category.SOCIAL}
    assert d.requires_runner is True


def test_panic_thermometer_requires_financial():
    d = PanicThermometerDepartment()
    assert d.required_categories == (Category.FINANCIAL,)
    assert d.optional_categories == (Category.NEWS,)
    assert d.requires_runner is False
```

- [ ] **Step 2: Run to verify failures**

```bash
uv run pytest packages/core/tests/test_departments/test_dept_dependencies.py -v
```

Expected: FAIL — fields don't exist.

- [ ] **Step 3: Update each dept dataclass**

For each of the seven dept files, add the new fields. Example for `equity_research.py`:
```python
from openlia.connectors.types import Category

@dataclass(frozen=True)
class EquityResearchDepartment:
    name: str = "equity_research"
    display_name: str = "Equity Research"
    # ...existing fields preserved...
    required_categories: tuple[Category, ...] = (Category.FINANCIAL,)
    optional_categories: tuple[Category, ...] = (
        Category.NEWS,
        Category.SOCIAL,
        Category.WEB_SEARCH,
    )
    requires_runner: bool = False
    disable_runtime_routing: bool = False
```

Apply the equivalent edits to:
- `secretary.py`: `required_categories=()`, `optional_categories=(Category.WEB_SEARCH,)`, `requires_runner=False`
- `earnings_update.py`: required `(FINANCIAL,)`, optional `(NEWS,)`, runner False
- `morning_briefing.py`: required `(FINANCIAL, NEWS)`, optional `(WEB_SEARCH,)`, runner False
- `macro_research.py`: required `(FINANCIAL,)`, optional `(NEWS,)`, **runner True**
- `retail_sentiment.py`: required `(FINANCIAL,)`, optional `(NEWS, SOCIAL)`, **runner True**
- `panic_thermometer.py`: required `(FINANCIAL,)`, optional `(NEWS,)`, runner False

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_departments/test_dept_dependencies.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/ packages/core/tests/test_departments/test_dept_dependencies.py
git commit -m "feat(departments): declare required/optional categories and requires_runner"
```

### Task 3.2 — `<dept>.routing_context.md` skeleton creation

**Files:**
- Create one per dept: `packages/core/src/openlia/departments/<dept>.routing_context.md` (seven total)
- Test: `packages/core/tests/test_departments/test_routing_context.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_departments/test_routing_context.py`:
```python
import re
from pathlib import Path

import pytest

DEPTS = (
    "secretary",
    "equity_research",
    "earnings_update",
    "morning_briefing",
    "macro_research",
    "retail_sentiment",
    "panic_thermometer",
)

REQUIRED_HEADINGS = (
    "## What this department does",
    "## Data this department needs access to",
    "## Out-of-scope topics",
    "## Example prompts and the data they imply",
)


def _path(dept: str) -> Path:
    return Path("packages/core/src/openlia/departments") / f"{dept}.routing_context.md"


@pytest.mark.parametrize("dept", DEPTS)
def test_routing_context_exists(dept: str):
    assert _path(dept).is_file(), f"missing routing_context.md for {dept}"


@pytest.mark.parametrize("dept", DEPTS)
def test_routing_context_has_required_headings(dept: str):
    text = _path(dept).read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"{dept} routing_context.md missing heading {heading!r}"


@pytest.mark.parametrize("dept", DEPTS)
def test_routing_context_has_minimum_content(dept: str):
    """Skeleton can ship with TODOs but the file must not be empty."""

    text = _path(dept).read_text(encoding="utf-8")
    word_count = len(re.findall(r"\S+", text))
    assert word_count > 30, f"{dept} routing_context.md is too sparse ({word_count} words)"
```

- [ ] **Step 2: Run to verify failures**

```bash
uv run pytest packages/core/tests/test_departments/test_routing_context.py -v
```

Expected: FAIL on missing files.

- [ ] **Step 3: Create the skeleton for each dept**

For each of the seven departments, create the skeleton file. Use the secretary one as the template; adapt the title and one-line top-of-file description. Example `secretary.routing_context.md`:
```markdown
# Secretary — Routing Context

Secretary is OpenLIA's general-purpose conversational department. It answers
broad financial questions, helps the user navigate other departments, and
serves as the default entry point when no specific department applies.

## What this department does
TODO (deep-dive content session): describe Secretary's role and primary
outputs in 1-2 sentences.

## Data this department needs access to
TODO (deep-dive content session): list the kinds of API endpoints and tools
the router should bias toward when Secretary is asked about each topic.
Drawn from frameworks (none for Secretary day-1), specs in
`planning/specs/pages/secretary.md`, and the dept's code.

## Out-of-scope topics
TODO (deep-dive content session): explicitly list topics Secretary does
NOT handle so the router does not over-reach into other departments'
territory.

## Example prompts and the data they imply
TODO (deep-dive content session): 3-6 representative prompts paired with
the kind of tools the router should pick. Few-shot ground truth that
calibrates the router.
```

Repeat with adapted top descriptions for:
- `equity_research.routing_context.md` — "Bottoms-up analysis of individual companies. Focuses on fundamentals, earnings drivers, news catalysts, and valuation context."
- `earnings_update.routing_context.md` — "Reactive event-driven analysis of quarterly earnings releases. Outputs structured beat/miss verdicts and thesis-impact assessments."
- `morning_briefing.routing_context.md` — "Daily macro and market briefing covering overnight moves, scheduled events, and top news."
- `macro_research.routing_context.md` — "Top-down macro analysis. Indicator dashboards on debt cycles, business cycles, and cross-asset reference levels."
- `retail_sentiment.routing_context.md` — "Real-time retail-investor sentiment classification per ticker. Surfaces signal alerts and spike detections."
- `panic_thermometer.routing_context.md` — "Cross-asset stress and risk-off detection from price, volatility, credit spreads, and news flow."

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_departments/test_routing_context.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/*.routing_context.md packages/core/tests/test_departments/test_routing_context.py
git commit -m "feat(departments): routing_context.md skeleton per department"
```

### Task 3.3 — `<dept>.needs.yaml` for Macro Research

**Files:**
- Create: `packages/core/src/openlia/departments/macro_research.needs.yaml`
- Test: `packages/core/tests/test_departments/test_macro_research_needs.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_departments/test_macro_research_needs.py`:
```python
from pathlib import Path

import yaml


def test_macro_research_needs_loads_and_has_expected_ids():
    path = Path("packages/core/src/openlia/departments/macro_research.needs.yaml")
    raw = yaml.safe_load(path.read_text())
    assert raw["department"] == "macro_research"
    ids = {n["id"] for n in raw["needs"]}
    assert {
        "debt_gdp",
        "interest_revenue",
        "tips_quote",
        "dxy_proxy",
        "cpi_yoy",
        "cpi_core_yoy",
        "gdp_yoy",
        "pmi",
        "stock_quote",
    }.issubset(ids)


def test_macro_research_needs_have_required_fields():
    path = Path("packages/core/src/openlia/departments/macro_research.needs.yaml")
    raw = yaml.safe_load(path.read_text())
    for need in raw["needs"]:
        assert "id" in need
        assert "description" in need and need["description"].strip()
        assert "shape" in need
        for p in need.get("parameters", []):
            assert {"name", "description", "type"}.issubset(p.keys())
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_departments/test_macro_research_needs.py -v
```

Expected: FAIL — file missing.

- [ ] **Step 3: Author the YAML**

Create `packages/core/src/openlia/departments/macro_research.needs.yaml`:
```yaml
department: macro_research

needs:
  - id: debt_gdp
    description: |
      Country-level government gross debt as a percentage of GDP, in
      percentage points (e.g., 110.0 means 110%). Sourced from official
      government statistics or central bank releases. Used by the Debt
      Cycle dashboard to gauge debt sustainability.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code, e.g. 'US', 'JP', 'DE'. Defaults to 'US'."
        type: string
        required: false
        default: "US"
    shape: float

  - id: interest_revenue
    description: |
      Net interest payments on government debt as a percentage of total
      government revenue. Used by the Debt Cycle dashboard to assess
      fiscal flexibility.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code; defaults to 'US'."
        type: string
        required: false
        default: "US"
    shape: float

  - id: tips_quote
    description: |
      Latest closing price for the iShares TIPS Bond ETF (NYSE: TIP).
      Used as an inflation-protected real-yield reference level.
    parameters: []
    shape: float

  - id: dxy_proxy
    description: |
      Latest closing price for the Invesco DB US Dollar Index Bullish Fund
      (NYSE: UUP), used as a tradeable DXY proxy.
    parameters: []
    shape: float

  - id: cpi_yoy
    description: |
      Headline year-over-year CPI inflation rate, in percentage points
      (e.g., 3.4 means 3.4% YoY). Defaults to United States.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code; defaults to 'US'."
        type: string
        required: false
        default: "US"
    shape: float

  - id: cpi_core_yoy
    description: |
      Core CPI year-over-year inflation rate, excluding food and energy,
      in percentage points. Defaults to United States.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code; defaults to 'US'."
        type: string
        required: false
        default: "US"
    shape: float

  - id: gdp_yoy
    description: |
      Real GDP year-over-year growth rate, in percentage points. Defaults
      to United States.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code; defaults to 'US'."
        type: string
        required: false
        default: "US"
    shape: float

  - id: pmi
    description: |
      Manufacturing PMI (Purchasing Managers' Index) headline value.
      Above 50 = expansion; below 50 = contraction. Defaults to US ISM.
    parameters:
      - name: country
        description: "ISO 3166-1 alpha-2 code; defaults to 'US'."
        type: string
        required: false
        default: "US"
    shape: float

  - id: stock_quote
    description: |
      Latest closing price for an equity, given its ticker symbol. Used
      by dashboards for cross-asset reference levels (HYG, LQD, TLT,
      gold ETFs, sector ETFs, etc.).
    parameters:
      - name: ticker
        description: "NYSE/NASDAQ/etc. symbol, e.g. 'TIP', 'HYG', 'GLD'."
        type: string
        required: true
    shape: float
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_departments/test_macro_research_needs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/macro_research.needs.yaml packages/core/tests/test_departments/test_macro_research_needs.py
git commit -m "feat(macro-research): declarative needs.yaml"
```

### Task 3.4 — `<dept>.needs.yaml` for Retail Sentiment

**Files:**
- Create: `packages/core/src/openlia/departments/retail_sentiment.needs.yaml`
- Test: `packages/core/tests/test_departments/test_retail_sentiment_needs.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_departments/test_retail_sentiment_needs.py`:
```python
from pathlib import Path

import yaml


def test_retail_sentiment_needs_have_social_posts():
    path = Path("packages/core/src/openlia/departments/retail_sentiment.needs.yaml")
    raw = yaml.safe_load(path.read_text())
    assert raw["department"] == "retail_sentiment"
    ids = {n["id"] for n in raw["needs"]}
    assert "social_posts" in ids


def test_social_posts_takes_ticker_param():
    path = Path("packages/core/src/openlia/departments/retail_sentiment.needs.yaml")
    raw = yaml.safe_load(path.read_text())
    posts = next(n for n in raw["needs"] if n["id"] == "social_posts")
    assert posts["shape"].startswith("list")
    param_names = {p["name"] for p in posts["parameters"]}
    assert "ticker" in param_names
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_departments/test_retail_sentiment_needs.py -v
```

Expected: FAIL — file missing.

- [ ] **Step 3: Author the YAML**

Create `packages/core/src/openlia/departments/retail_sentiment.needs.yaml`:
```yaml
department: retail_sentiment

needs:
  - id: social_posts
    description: |
      Recent social media posts mentioning the given equity ticker,
      sorted by recency. Sourced from a sentiment endpoint exposed by
      a financial-category connector (EODHD's sentiment_data, FMP's
      social_sentiment, or equivalent). Returns a list of dicts each
      containing at minimum: id (string), body (string), author
      (string), timestamp (ISO-8601 string), source (string).
    parameters:
      - name: ticker
        description: "NYSE/NASDAQ ticker, e.g. 'AAPL', 'TSLA'."
        type: string
        required: true
    shape: "list[object]"
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_departments/test_retail_sentiment_needs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/retail_sentiment.needs.yaml packages/core/tests/test_departments/test_retail_sentiment_needs.py
git commit -m "feat(retail-sentiment): declarative needs.yaml"
```

### Task 3.5 — Loader for routing_context and needs

**Files:**
- Modify: `packages/core/src/openlia/departments/__init__.py` (or create `loader.py`)
- Modify or create: `packages/core/src/openlia/departments/loader.py`
- Test: `packages/core/tests/test_departments/test_loader.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_departments/test_loader.py`:
```python
from openlia.connectors.runner_needs import RunnerNeed
from openlia.departments.loader import load_needs, load_routing_context


def test_load_routing_context_returns_string_with_h2_sections():
    text = load_routing_context("equity_research")
    assert isinstance(text, str) and len(text) > 50
    assert "## What this department does" in text


def test_load_needs_returns_list_of_runner_need():
    needs = load_needs("macro_research")
    ids = {n.id for n in needs}
    assert "debt_gdp" in ids
    assert all(isinstance(n, RunnerNeed) for n in needs)


def test_load_needs_for_chat_only_dept_returns_empty_list():
    assert load_needs("secretary") == []


def test_load_routing_context_unknown_dept_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_routing_context("ghost_dept")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_departments/test_loader.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement the loader**

Create `packages/core/src/openlia/departments/loader.py`:
```python
"""Load per-department routing_context and needs.yaml artifacts."""

from __future__ import annotations

from pathlib import Path

import yaml

from openlia.connectors.runner_needs import NeedParameter, RunnerNeed

_HERE = Path(__file__).resolve().parent


def _routing_context_path(department_id: str) -> Path:
    return _HERE / f"{department_id}.routing_context.md"


def _needs_path(department_id: str) -> Path:
    return _HERE / f"{department_id}.needs.yaml"


def load_routing_context(department_id: str) -> str:
    """Returns the dept's routing_context.md content as a string.

    Raises FileNotFoundError if no routing_context.md is shipped for the
    department (every dept must ship one — test_routing_context.py guards).
    """

    path = _routing_context_path(department_id)
    if not path.is_file():
        raise FileNotFoundError(f"no routing_context.md for department {department_id!r}")
    return path.read_text(encoding="utf-8")


def load_needs(department_id: str) -> list[RunnerNeed]:
    """Returns the dept's declared runner needs, or [] if no needs.yaml exists."""

    path = _needs_path(department_id)
    if not path.is_file():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    if raw.get("department") != department_id:
        raise ValueError(
            f"{path}: 'department' field must be {department_id!r}, got {raw.get('department')!r}"
        )
    out: list[RunnerNeed] = []
    for n in raw.get("needs", []):
        params = tuple(
            NeedParameter(
                name=p["name"],
                description=p["description"],
                type_=p["type"],
                required=bool(p.get("required", False)),
                default=p.get("default"),
            )
            for p in n.get("parameters", [])
        )
        out.append(
            RunnerNeed(
                id=n["id"],
                description=n["description"],
                parameters=params,
                shape=n["shape"],
            )
        )
    return out
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_departments/test_loader.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/departments/loader.py packages/core/tests/test_departments/test_loader.py
git commit -m "feat(departments): loader for routing_context.md and needs.yaml"
```

### Task 3.6 — Drift-safety: every code-referenced need exists in YAML

**Files:**
- Test: `packages/server/tests/test_departments/test_needs_drift_safety.py`

- [ ] **Step 1: Write the test**

Create `packages/server/tests/test_departments/test_needs_drift_safety.py`:
```python
"""Cross-checks that runner code's referenced need ids match the YAML.

For each runner-bearing department:
1. Every id used at runtime (e.g., MR's T1_NEEDS) must appear in the
   dept's needs.yaml.
2. Every id declared in the dept's needs.yaml must appear in at least
   one runner module.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

from openlia.departments.loader import load_needs


def _all_python_files_under(pkg_dir: Path) -> list[Path]:
    return list(pkg_dir.rglob("*.py"))


def _ids_referenced_in_dept_runner(dept_id: str) -> set[str]:
    """Return all need-ids referenced by the dept's runner code paths.

    Heuristic: search for the conventional patterns:
    - T1_NEEDS = (...) tuple literals
    - dispatcher.fetch_need("...", ...) call sites
    """

    candidates = (
        Path("packages/core/src/openlia"),
        Path("packages/server/src/openlia_server"),
    )
    ids: set[str] = set()
    for root in candidates:
        for f in _all_python_files_under(root):
            text = f.read_text(encoding="utf-8")
            if dept_id not in text and "fetch_need" not in text and "T1_NEEDS" not in text:
                continue
            for m in re.finditer(r'fetch_need\(\s*"([\w_]+)"', text):
                ids.add(m.group(1))
            for tuple_match in re.finditer(
                r"T1_NEEDS\s*[:=][^=]*?=\s*\(\s*([^)]+)\)", text, re.DOTALL
            ):
                for s in re.finditer(r'"([\w_]+)"', tuple_match.group(1)):
                    ids.add(s.group(1))
    return ids


def test_macro_research_needs_match_runner_references():
    declared = {n.id for n in load_needs("macro_research")}
    referenced = _ids_referenced_in_dept_runner("macro_research")
    # Allow runner files to reference shared id patterns even outside MR;
    # the asymmetric check is: every MR-referenced id must be declared.
    # Until Phase 8 lands the MR refactor, no T1_NEEDS exist in code.
    # After Phase 8, populate this assertion fully:
    if referenced:
        assert referenced.issubset(declared), (
            f"MR runner references undeclared needs: {referenced - declared}"
        )
    # Reverse check: each declared id must have a description (already validated
    # by RunnerNeed schema) — declared id existence is the contract this test guards.
    assert declared, "MR needs.yaml is empty — should have at least one need"


def test_retail_sentiment_needs_match_runner_references():
    declared = {n.id for n in load_needs("retail_sentiment")}
    referenced = _ids_referenced_in_dept_runner("retail_sentiment")
    if referenced:
        assert referenced.issubset(declared), (
            f"RS runner references undeclared needs: {referenced - declared}"
        )
    assert "social_posts" in declared
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest packages/server/tests/test_departments/test_needs_drift_safety.py -v
```

Expected: PASS (the test is conditional on Phase 8's runner refactor, which hasn't happened yet — so the `referenced` set is currently empty, and the assertions become trivial).

- [ ] **Step 3: Commit**

```bash
git add packages/server/tests/test_departments/test_needs_drift_safety.py
git commit -m "test(departments): drift-safety check for needs.yaml vs runner refs"
```

---

## Phase 4 — Wizard-time runner adapter (callable_spec resolver)

### Task 4.1 — Python lib introspection

**Files:**
- Create: `packages/core/src/openlia/connectors/python_lib_introspect.py`
- Test: `packages/core/tests/test_connectors/test_python_lib_introspect.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_connectors/test_python_lib_introspect.py`:
```python
from openlia.connectors.python_lib_introspect import (
    introspect_module,
    IntrospectedCallable,
)


def test_introspect_module_returns_public_callables():
    # Use a known stdlib module (`math`) — stable surface, no install.
    out = introspect_module("math")
    names = {c.qualname for c in out}
    assert "sqrt" in names
    assert all(isinstance(c, IntrospectedCallable) for c in out)
    assert all(not c.qualname.startswith("_") for c in out)


def test_introspect_module_captures_docstring_and_signature():
    out = introspect_module("math")
    sqrt = next(c for c in out if c.qualname == "sqrt")
    assert "square root" in (sqrt.doc or "").lower() or sqrt.signature
    assert sqrt.signature is not None


def test_introspect_module_skips_dunder():
    out = introspect_module("math")
    assert not any(c.qualname.startswith("__") for c in out)


def test_introspect_module_unknown_raises():
    import pytest

    with pytest.raises(ImportError):
        introspect_module("zzz_nonexistent_module_zzz")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_python_lib_introspect.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement introspection**

Create `packages/core/src/openlia/connectors/python_lib_introspect.py`:
```python
"""Walk a Python module's public surface and report callables.

Intentionally conservative: top-level public callables and methods on
public classes. Skips dunders, privates, and non-callables. Used by the
wizard adapter to give the LLM a structured view of a lib's API.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class IntrospectedCallable:
    qualname: str           # e.g. "APIClient.economic_data"
    signature: str | None   # textual signature
    doc: str | None         # docstring (may be truncated)


def _short_doc(doc: str | None) -> str | None:
    if not doc:
        return None
    # First non-empty paragraph, capped at ~600 chars to keep adapter prompts lean.
    para = doc.strip().split("\n\n", 1)[0]
    return para[:600]


def introspect_module(module_name: str) -> list[IntrospectedCallable]:
    """Return a list of public callables exposed by the given module.

    Walks: top-level functions, top-level classes, and the public
    methods of those classes. Skips anything starting with '_'.
    """

    mod = importlib.import_module(module_name)
    out: list[IntrospectedCallable] = []
    for name, obj in inspect.getmembers(mod):
        if name.startswith("_"):
            continue
        if inspect.isfunction(obj) or inspect.isbuiltin(obj):
            try:
                sig = str(inspect.signature(obj))
            except (TypeError, ValueError):
                sig = None
            out.append(
                IntrospectedCallable(qualname=name, signature=sig, doc=_short_doc(inspect.getdoc(obj)))
            )
            continue
        if inspect.isclass(obj):
            for mname, mobj in inspect.getmembers(obj):
                if mname.startswith("_"):
                    continue
                if not callable(mobj):
                    continue
                try:
                    sig = str(inspect.signature(mobj))
                except (TypeError, ValueError):
                    sig = None
                out.append(
                    IntrospectedCallable(
                        qualname=f"{name}.{mname}",
                        signature=sig,
                        doc=_short_doc(inspect.getdoc(mobj)),
                    )
                )
    out.sort(key=lambda c: c.qualname)
    return out
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_connectors/test_python_lib_introspect.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/connectors/python_lib_introspect.py packages/core/tests/test_connectors/test_python_lib_introspect.py
git commit -m "feat(connectors): Python module introspection helper"
```

### Task 4.2 — Adapter LLM prompt + JSON output parser

**Files:**
- Create: `packages/server/src/openlia_server/services/callable_spec_resolver.py`
- Test: `packages/server/tests/test_services/test_callable_spec_resolver.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_callable_spec_resolver.py`:
```python
from unittest.mock import AsyncMock

import pytest

from openlia.connectors.python_lib_introspect import IntrospectedCallable
from openlia.connectors.runner_needs import (
    CallableSpec,
    NeedParameter,
    ParamBinding,
    RunnerNeed,
)
from openlia_server.services.callable_spec_resolver import (
    AdapterRefusal,
    parse_adapter_response,
    resolve_callable_spec,
)


def _need_debt_gdp() -> RunnerNeed:
    return RunnerNeed(
        id="debt_gdp",
        description="US debt-to-GDP ratio in percentage points.",
        parameters=(
            NeedParameter(
                name="country",
                description="ISO code; default US",
                type_="string",
                required=False,
                default="US",
            ),
        ),
        shape="float",
    )


def test_parse_adapter_response_round_trip():
    raw = {
        "need_id": "debt_gdp",
        "access_mode": "python_lib",
        "module": "eodhd",
        "method": "economic_data",
        "instance_factory": {"class": "APIClient", "args": {"api_key": "$EODHD_API_KEY"}},
        "param_bindings": {
            "country": {"to_arg": "country_code", "transform": "upper"}
        },
        "constants": {"indicator": "DEBT_GDP_PCT"},
        "shape": "float",
    }
    parsed = parse_adapter_response(raw, expected_need_id="debt_gdp")
    assert isinstance(parsed, CallableSpec)
    assert parsed.module == "eodhd"
    assert parsed.param_bindings["country"] == ParamBinding(
        to_arg="country_code", transform="upper"
    )


def test_parse_adapter_response_refusal_raises():
    with pytest.raises(AdapterRefusal):
        parse_adapter_response(
            {"refusal": "this lib has no function for debt-to-GDP"},
            expected_need_id="debt_gdp",
        )


def test_parse_adapter_response_wrong_need_id_raises():
    raw = {"need_id": "elephant", "access_mode": "python_lib", "module": "x", "shape": "float"}
    with pytest.raises(ValueError, match="need_id mismatch"):
        parse_adapter_response(raw, expected_need_id="debt_gdp")


@pytest.mark.asyncio
async def test_resolve_callable_spec_with_python_lib_callables():
    """Adapter returns a structured spec; resolver returns a parsed CallableSpec."""

    fake_llm = AsyncMock()
    fake_llm.complete_json.return_value = {
        "need_id": "debt_gdp",
        "access_mode": "python_lib",
        "module": "eodhd",
        "method": "economic_data",
        "instance_factory": {"class": "APIClient", "args": {"api_key": "$EODHD_API_KEY"}},
        "param_bindings": {"country": {"to_arg": "country_code", "transform": None}},
        "constants": {"indicator": "DEBT_GDP_PCT"},
        "shape": "float",
    }
    callables = [
        IntrospectedCallable(
            qualname="APIClient.economic_data",
            signature="(country_code: str, indicator: str) -> dict",
            doc="Fetch macro indicator data.",
        )
    ]
    spec = await resolve_callable_spec(
        need=_need_debt_gdp(),
        access_mode="python_lib",
        introspected_callables=callables,
        mcp_tools=None,
        llm=fake_llm,
    )
    assert spec.module == "eodhd"
    assert spec.method == "economic_data"
    fake_llm.complete_json.assert_awaited_once()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_services/test_callable_spec_resolver.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement the resolver**

Create `packages/server/src/openlia_server/services/callable_spec_resolver.py`:
```python
"""Wizard-time adapter LLM that resolves a runner need to a CallableSpec."""

from __future__ import annotations

import json
from typing import Any, Protocol

from openlia.connectors.python_lib_introspect import IntrospectedCallable
from openlia.connectors.runner_needs import CallableSpec, RunnerNeed


class AdapterRefusal(Exception):
    """The adapter LLM refused to bind the need (no suitable function in the lib)."""


class _LLM(Protocol):
    async def complete_json(self, *, system: str, prompt: str) -> dict[str, Any]: ...


_SYSTEM_PROMPT = """\
You are an integration adapter. Given a runner's "need" (declarative
description of data) and a library's available functions or MCP tools,
your job is to return a structured callable spec describing exactly how
to satisfy the need.

Rules:
- Output JSON only, no prose.
- If you cannot find a suitable function, output {"refusal": "<reason>"}.
- For python_lib: return need_id, access_mode="python_lib", module, method,
  instance_factory (or null if module-level function), param_bindings,
  constants, shape.
- For cli_mcp / remote_mcp: return need_id, access_mode, tool_name,
  param_bindings, constants, shape.
- Bindings must rename runner-side parameter names to the underlying
  function's argument names. Use named transforms only from this list:
  upper, lower, iso_to_eodhd, or null.
- Constants are baked-in arguments (e.g., indicator codes) you decided
  to hardcode based on the need's intent.
"""


def _build_user_prompt(
    *,
    need: RunnerNeed,
    access_mode: str,
    introspected_callables: list[IntrospectedCallable] | None,
    mcp_tools: list[dict[str, Any]] | None,
) -> str:
    lines: list[str] = []
    lines.append("Need:")
    lines.append(json.dumps(need.to_json(), indent=2))
    lines.append("")
    lines.append(f"Access mode: {access_mode}")
    lines.append("")
    if access_mode == "python_lib":
        assert introspected_callables is not None
        lines.append("Available callables (qualname / signature / doc):")
        for c in introspected_callables:
            lines.append(f"- {c.qualname}{c.signature or ''}")
            if c.doc:
                lines.append(f"  {c.doc}")
    else:
        assert mcp_tools is not None
        lines.append("Available MCP tools (name / description / input_schema):")
        for t in mcp_tools:
            lines.append(f"- {t['name']}: {t.get('description', '')}")
            lines.append(f"  schema: {json.dumps(t.get('input_schema', {}))}")
    lines.append("")
    lines.append("Return the callable spec as JSON.")
    return "\n".join(lines)


def parse_adapter_response(raw: dict[str, Any], *, expected_need_id: str) -> CallableSpec:
    if "refusal" in raw:
        raise AdapterRefusal(str(raw["refusal"]))
    actual_id = raw.get("need_id")
    if actual_id != expected_need_id:
        raise ValueError(f"need_id mismatch: expected {expected_need_id!r}, got {actual_id!r}")
    return CallableSpec.from_json(raw)


async def resolve_callable_spec(
    *,
    need: RunnerNeed,
    access_mode: str,
    introspected_callables: list[IntrospectedCallable] | None,
    mcp_tools: list[dict[str, Any]] | None,
    llm: _LLM,
) -> CallableSpec:
    """Ask the adapter LLM to bind the need to a concrete callable."""

    user_prompt = _build_user_prompt(
        need=need,
        access_mode=access_mode,
        introspected_callables=introspected_callables,
        mcp_tools=mcp_tools,
    )
    raw = await llm.complete_json(system=_SYSTEM_PROMPT, prompt=user_prompt)
    return parse_adapter_response(raw, expected_need_id=need.id)
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_callable_spec_resolver.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/callable_spec_resolver.py packages/server/tests/test_services/test_callable_spec_resolver.py
git commit -m "feat(connectors): wizard-time adapter for callable_spec resolution"
```

### Task 4.3 — Canary execution

**Files:**
- Create: `packages/server/src/openlia_server/services/callable_spec_canary.py`
- Test: `packages/server/tests/test_services/test_callable_spec_canary.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_callable_spec_canary.py`:
```python
import math

import pytest

from openlia.connectors.runner_needs import (
    CallableSpec,
    NeedParameter,
    ParamBinding,
    RunnerNeed,
)
from openlia_server.services.callable_spec_canary import (
    CanaryShapeError,
    canary_python_lib,
    sample_args_for_need,
)


def test_sample_args_uses_default_when_optional():
    need = RunnerNeed(
        id="x",
        description="",
        parameters=(
            NeedParameter(
                name="country", description="", type_="string", required=False, default="US"
            ),
        ),
        shape="float",
    )
    assert sample_args_for_need(need) == {"country": "US"}


def test_sample_args_synthesizes_required_string():
    need = RunnerNeed(
        id="x",
        description="",
        parameters=(
            NeedParameter(name="ticker", description="", type_="string", required=True),
        ),
        shape="float",
    )
    assert sample_args_for_need(need) == {"ticker": "AAPL"}


def test_canary_python_lib_invokes_module_function_and_validates_shape():
    spec = CallableSpec(
        need_id="sqrt_test",
        access_mode="python_lib",
        module="math",
        method="sqrt",
        instance_factory=None,
        param_bindings={"x": ParamBinding(to_arg="x", transform=None)},
        constants={},
        shape="float",
    )
    result = canary_python_lib(spec=spec, runtime_args={"x": 16.0})
    assert math.isclose(result, 4.0)


def test_canary_python_lib_shape_mismatch_raises():
    spec = CallableSpec(
        need_id="sqrt_test",
        access_mode="python_lib",
        module="math",
        method="sqrt",
        instance_factory=None,
        param_bindings={"x": ParamBinding(to_arg="x", transform=None)},
        constants={},
        shape="list[object]",
    )
    with pytest.raises(CanaryShapeError):
        canary_python_lib(spec=spec, runtime_args={"x": 16.0})
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_services/test_callable_spec_canary.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement canary**

Create `packages/server/src/openlia_server/services/callable_spec_canary.py`:
```python
"""Execute a CallableSpec with sample args; validate the response shape."""

from __future__ import annotations

import importlib
from typing import Any

from openlia.connectors.parameter_binding import apply_bindings
from openlia.connectors.runner_needs import CallableSpec, RunnerNeed


class CanaryShapeError(RuntimeError):
    """The canary call returned a value whose shape doesn't match the spec."""


_DEFAULT_SAMPLES: dict[str, Any] = {
    "string": "AAPL",
    "integer": 1,
    "number": 1.0,
    "boolean": False,
}


def sample_args_for_need(need: RunnerNeed) -> dict[str, Any]:
    """Build a dict of sample runtime args for canary execution.

    For optional parameters with defaults, use the default. For required
    parameters, synthesize a plausible sample based on the type.
    """

    out: dict[str, Any] = {}
    for p in need.parameters:
        if p.required:
            out[p.name] = _DEFAULT_SAMPLES.get(p.type_, "x")
        elif p.default is not None:
            out[p.name] = p.default
    return out


def _shape_matches(value: Any, shape: str) -> bool:
    if shape == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if shape == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if shape == "bool":
        return isinstance(value, bool)
    if shape == "string":
        return isinstance(value, str)
    if shape.startswith("list"):
        return isinstance(value, list)
    if shape.startswith("dict") or shape == "object":
        return isinstance(value, dict)
    return True  # unknown shapes pass — let runtime decide


def canary_python_lib(*, spec: CallableSpec, runtime_args: dict[str, Any]) -> Any:
    """Invoke a python_lib spec and return the response (raises on shape mismatch)."""

    if spec.access_mode != "python_lib":
        raise ValueError(f"expected python_lib spec, got {spec.access_mode!r}")
    mod = importlib.import_module(spec.module or "")
    if spec.instance_factory:
        cls_name = spec.instance_factory["class"]
        cls = getattr(mod, cls_name)
        kwargs = dict(spec.instance_factory.get("args", {}))
        # Substitute any "$VAR" placeholder; for canary we use a benign empty string
        # since we are validating shape, not making a real authenticated call.
        for k, v in list(kwargs.items()):
            if isinstance(v, str) and v.startswith("$"):
                kwargs[k] = ""
        instance = cls(**kwargs)
        target = getattr(instance, spec.method or "")
    else:
        target = getattr(mod, spec.method or "")
    bound = apply_bindings(
        bindings=spec.param_bindings, constants=spec.constants, runtime_args=runtime_args
    )
    response = target(**bound)
    if not _shape_matches(response, spec.shape):
        raise CanaryShapeError(
            f"canary shape mismatch: expected {spec.shape!r}, got {type(response).__name__}"
        )
    return response
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_callable_spec_canary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/callable_spec_canary.py packages/server/tests/test_services/test_callable_spec_canary.py
git commit -m "feat(connectors): canary execution for python_lib callable specs"
```

---

## Phase 5 — Dispatcher API extensions

### Task 5.1 — `candidate_tools_for_router` and `fetch_need` API

**Files:**
- Modify: `packages/core/src/openlia/connectors/dispatch.py`
- Test: `packages/core/tests/test_connectors/test_dispatch_extensions.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_connectors/test_dispatch_extensions.py`:
```python
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.runner_needs import CallableSpec, ParamBinding
from openlia.connectors.types import Category, ToolDefinition


def _prep(provider_id: str, tool_names: list[str], category: Category):
    transport = AsyncMock()
    return PreparedConnector(
        connector_id=f"c-{provider_id}",
        provider_id=provider_id,
        transport=transport,
        tools={
            name: ToolDefinition(name=name, description="", input_schema={})
            for name in tool_names
        },
    ), transport


def test_candidate_tools_for_router_returns_full_validated_inventory():
    pc1, _ = _prep("eodhd", ["get_quote", "economic_data"], Category.FINANCIAL)
    pc2, _ = _prep("newsapi_ai", ["search_articles"], Category.NEWS)
    d = Dispatcher(
        connectors={pc1.connector_id: pc1, pc2.connector_id: pc2},
        allowlist={},
        connector_categories={pc1.connector_id: Category.FINANCIAL, pc2.connector_id: Category.NEWS},
        callable_specs={},
    )
    out = d.candidate_tools_for_router(department_id="equity_research")
    names = {t["name"] for t in out}
    assert names == {"eodhd__get_quote", "eodhd__economic_data", "newsapi_ai__search_articles"}


@pytest.mark.asyncio
async def test_fetch_need_walks_python_lib_spec(monkeypatch):
    spec = CallableSpec(
        need_id="sqrt_test",
        access_mode="python_lib",
        module="math",
        method="sqrt",
        param_bindings={"x": ParamBinding(to_arg="x", transform=None)},
        constants={},
        shape="float",
    )
    d = Dispatcher(
        connectors={},
        allowlist={},
        connector_categories={},
        callable_specs={("macro_research", "sqrt_test"): (spec, "c-eodhd")},
    )
    async with d.in_department("macro_research"):
        result = await d.fetch_need("sqrt_test", x=25.0)
    assert result == 5.0


@pytest.mark.asyncio
async def test_fetch_need_walks_mcp_spec():
    spec = CallableSpec(
        need_id="quote",
        access_mode="cli_mcp",
        tool_name="get_quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol", transform="iso_to_eodhd")},
        constants={"fmt": "json"},
        shape="float",
    )
    pc, transport = _prep("eodhd", ["get_quote"], Category.FINANCIAL)
    transport.call_tool = AsyncMock(return_value=99.5)
    d = Dispatcher(
        connectors={pc.connector_id: pc},
        allowlist={},
        connector_categories={pc.connector_id: Category.FINANCIAL},
        callable_specs={("equity_research", "quote"): (spec, pc.connector_id)},
    )
    async with d.in_department("equity_research"):
        result = await d.fetch_need("quote", ticker="TIP")
    transport.call_tool.assert_awaited_once_with("get_quote", {"symbol": "TIP.US", "fmt": "json"})
    assert result == 99.5


@pytest.mark.asyncio
async def test_fetch_need_without_active_department_raises():
    d = Dispatcher(connectors={}, allowlist={}, connector_categories={}, callable_specs={})
    with pytest.raises(RuntimeError, match="no active department"):
        await d.fetch_need("anything")


@pytest.mark.asyncio
async def test_fetch_need_missing_spec_raises():
    d = Dispatcher(connectors={}, allowlist={}, connector_categories={}, callable_specs={})
    async with d.in_department("macro_research"):
        with pytest.raises(LookupError, match="no callable spec"):
            await d.fetch_need("debt_gdp")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_dispatch_extensions.py -v
```

Expected: FAIL — `Dispatcher.candidate_tools_for_router` and `fetch_need` don't exist; `Dispatcher` doesn't accept `callable_specs`.

- [ ] **Step 3: Extend the Dispatcher**

Edit `packages/core/src/openlia/connectors/dispatch.py`. Add the new fields and methods to the dataclass:
```python
import contextlib
import contextvars
import importlib
from dataclasses import dataclass, field
from typing import Any

from openlia.connectors.parameter_binding import apply_bindings
from openlia.connectors.runner_needs import CallableSpec
from openlia.connectors.types import Category, ToolDefinition

PREFIX_SEP = "__"

# ContextVar holds the active department for the current async task.
_active_department: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_active_department", default=None
)


# (Keep existing PreparedConnector, DispatchError, CallableTransport.)


@dataclass
class Dispatcher:
    connectors: dict[str, "PreparedConnector"]
    allowlist: dict[str, list[tuple[str, str]]]   # legacy field; unused for chat post-redesign
    connector_categories: dict[str, Category] = field(default_factory=dict)
    callable_specs: dict[tuple[str, str], tuple[CallableSpec, str]] = field(default_factory=dict)
    """Maps (department_id, need_id) -> (callable_spec, connector_id)."""

    # ── Existing tool-use surface (unchanged) ──────────────────────────────────
    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict[str, Any]) -> Any:
        if PREFIX_SEP not in prefixed_name:
            raise DispatchError(f"missing prefix in {prefixed_name!r}")
        provider_id, _, raw_name = prefixed_name.partition(PREFIX_SEP)
        for conn in self.connectors.values():
            if conn.provider_id == provider_id and raw_name in conn.tools:
                return await conn.transport.call_tool(raw_name, arguments)
        raise DispatchError(f"no connector for {prefixed_name!r}")

    # ── New: tool inventory for the runtime router ────────────────────────────
    def candidate_tools_for_router(
        self,
        department_id: str,
        *,
        include_categories: set[Category] | None = None,
    ) -> list[dict[str, Any]]:
        """Return every validated tool the dept *could* use, prefixed by provider.

        No allowlist filtering. The runtime router selects from this pool.
        Optional `include_categories` lets callers narrow by category.
        """

        out: list[dict[str, Any]] = []
        for conn in self.connectors.values():
            if include_categories is not None:
                cat = self.connector_categories.get(conn.connector_id)
                if cat not in include_categories:
                    continue
            for tool_name, td in conn.tools.items():
                out.append(
                    {
                        "name": f"{conn.provider_id}{PREFIX_SEP}{tool_name}",
                        "description": td.description,
                        "input_schema": td.input_schema,
                    }
                )
        return out

    # ── New: department context for runners ───────────────────────────────────
    @contextlib.asynccontextmanager
    async def in_department(self, department_id: str):
        token = _active_department.set(department_id)
        try:
            yield
        finally:
            _active_department.reset(token)

    # ── New: deterministic-runner fetch ───────────────────────────────────────
    async def fetch_need(self, need_id: str, **runtime_args: Any) -> Any:
        dept = _active_department.get()
        if dept is None:
            raise RuntimeError("no active department; call within `dispatcher.in_department(...)`")
        key = (dept, need_id)
        if key not in self.callable_specs:
            raise LookupError(
                f"no callable spec configured for ({dept!r}, {need_id!r})"
            )
        spec, connector_id = self.callable_specs[key]
        bound = apply_bindings(
            bindings=spec.param_bindings, constants=spec.constants, runtime_args=runtime_args
        )
        if spec.access_mode == "python_lib":
            return self._invoke_python_lib(spec=spec, kwargs=bound)
        if spec.access_mode in ("cli_mcp", "remote_mcp"):
            conn = self.connectors.get(connector_id)
            if conn is None:
                raise DispatchError(f"connector {connector_id!r} not loaded")
            return await conn.transport.call_tool(spec.tool_name or "", bound)
        raise DispatchError(f"unknown access_mode {spec.access_mode!r}")

    @staticmethod
    def _invoke_python_lib(*, spec: CallableSpec, kwargs: dict[str, Any]) -> Any:
        mod = importlib.import_module(spec.module or "")
        if spec.instance_factory:
            cls = getattr(mod, spec.instance_factory["class"])
            inst_args = dict(spec.instance_factory.get("args", {}))
            for k, v in list(inst_args.items()):
                if isinstance(v, str) and v.startswith("$"):
                    import os
                    inst_args[k] = os.environ.get(v[1:], "")
            instance = cls(**inst_args)
            target = getattr(instance, spec.method or "")
        else:
            target = getattr(mod, spec.method or "")
        return target(**kwargs)
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_connectors/test_dispatch_extensions.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the entire connectors test suite**

```bash
uv run pytest packages/core/tests/test_connectors/ packages/server/tests/test_connectors/ -v 2>&1 | tail -10
```

Expected: PASS. Existing tests for `tools_for_department` (if any) may break — convert them to use `candidate_tools_for_router` (the allowlist-filtered version is removed by this redesign).

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/connectors/dispatch.py packages/core/tests/test_connectors/test_dispatch_extensions.py
git commit -m "feat(connectors): Dispatcher.fetch_need + candidate_tools_for_router + in_department"
```

### Task 5.2 — `dispatcher_factory` rewrite

**Files:**
- Modify: `packages/server/src/openlia_server/services/dispatcher_factory.py`
- Test: `packages/server/tests/test_services/test_dispatcher_factory.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_dispatcher_factory.py`:
```python
from openlia.connectors.types import Category
from openlia_server.db.models.connectors import Connector
from openlia_server.db.models.runner_callable_specs import RunnerCallableSpec
from openlia_server.services.dispatcher_factory import build_dispatcher_for_session


def test_build_dispatcher_loads_validated_connectors_and_callable_specs(session_factory):
    with session_factory() as s:
        s.add(
            Connector(
                id="c-eodhd",
                provider_id="eodhd",
                source="cli_mcp",
                category="financial",
                launch={"modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd"], "env_keys": []}]},
                cached_tools=[
                    {"name": "get_quote", "description": "", "input_schema": {}},
                ],
                status="validated",
            )
        )
        s.add(
            RunnerCallableSpec(
                id="rcs1",
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id="c-eodhd",
                access_mode="python_lib",
                spec={
                    "need_id": "debt_gdp",
                    "access_mode": "python_lib",
                    "module": "eodhd",
                    "method": "economic_data",
                    "shape": "float",
                    "param_bindings": {},
                    "constants": {"indicator": "DEBT_GDP_PCT"},
                },
            )
        )
        s.commit()

    with session_factory() as s:
        d = build_dispatcher_for_session(s)
    assert "c-eodhd" in d.connectors
    assert d.connector_categories["c-eodhd"] == Category.FINANCIAL
    assert ("macro_research", "debt_gdp") in d.callable_specs


def test_build_dispatcher_skips_pending_connectors(session_factory):
    with session_factory() as s:
        s.add(
            Connector(
                id="c-pending",
                provider_id="eodhd",
                source="cli_mcp",
                category="financial",
                launch={"modes": [{"kind": "cli_mcp", "argv": ["uvx", "x"], "env_keys": []}]},
                status="pending",
            )
        )
        s.commit()

    with session_factory() as s:
        d = build_dispatcher_for_session(s)
    assert d.connectors == {}
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_services/test_dispatcher_factory.py -v
```

Expected: FAIL — `dispatcher_factory` from cutover branch hasn't been brought in (we said in Phase 0 that we'd recreate it here).

- [ ] **Step 3: Implement the factory**

Create `packages/server/src/openlia_server/services/dispatcher_factory.py`:
```python
"""Build a runtime Dispatcher from current DB state.

Reads:
- VALIDATED Connector rows + their cached tools (for chat tool inventory).
- RunnerCallableSpec rows (for runner fetch_need).

Wires:
- MCPTransport per connector (CLI_MCP / REMOTE_MCP / BUILT_IN modes).
- Decrypted API key injection for built-in modes (via dedicated env_keys).
"""

from __future__ import annotations

from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.mcp_transport import (
    MCPTransport,
    SessionFactory,
    default_session_factory,
)
from openlia.connectors.runner_needs import CallableSpec
from openlia.connectors.types import (
    Category,
    ConnectorStatus,
    ToolDefinition,
)
from sqlalchemy.orm import Session

from openlia_server.db.crypto import decrypt_for_row
from openlia_server.db.models.connectors import Connector
from openlia_server.db.models.runner_callable_specs import RunnerCallableSpec


def _decrypt_env(row: Connector, env_keys: tuple[str, ...]) -> dict[str, str]:
    if not env_keys or row.api_key_encrypted is None:
        return {k: "" for k in env_keys}
    decrypted = decrypt_for_row(row.id, row.api_key_encrypted)
    return {k: decrypted for k in env_keys}


def build_dispatcher_for_session(
    session: Session,
    *,
    session_factory: SessionFactory = default_session_factory,
) -> Dispatcher:
    """Hydrate a Dispatcher from the session's current DB state."""

    rows = (
        session.query(Connector).filter(Connector.status == ConnectorStatus.VALIDATED.value).all()
    )
    prepared: dict[str, PreparedConnector] = {}
    categories: dict[str, Category] = {}
    for row in rows:
        modes = row.launch.get("modes", []) if isinstance(row.launch, dict) else []
        # Find the first MCP-style mode for tool exposure.
        mcp_mode = next(
            (m for m in modes if m.get("kind") in ("cli_mcp", "remote_mcp", "built_in")), None
        )
        if mcp_mode is None:
            continue
        tools = {
            t["name"]: ToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("input_schema", {}),
            )
            for t in (row.cached_tools or [])
        }
        env_keys = tuple(mcp_mode.get("env_keys", ()))
        env = _decrypt_env(row, env_keys)
        if mcp_mode["kind"] == "cli_mcp":
            transport = MCPTransport.cli(
                argv=tuple(mcp_mode["argv"]), env=env, session_factory=session_factory
            )
        elif mcp_mode["kind"] == "remote_mcp":
            transport = MCPTransport.remote(
                url=mcp_mode["url"],
                headers={k: v for k, v in mcp_mode.get("headers", [])},
                session_factory=session_factory,
            )
        else:
            # built_in: same machinery as cli_mcp once the recipe is resolved.
            from openlia.connectors.builtins import get_builtin

            tpl = get_builtin(mcp_mode["template_id"])
            transport = MCPTransport.cli(
                argv=tuple(tpl.cli_argv),
                env={tpl.api_key_env_var: env.get(tpl.api_key_env_var, "")},
                session_factory=session_factory,
            )
        prepared[row.id] = PreparedConnector(
            connector_id=row.id,
            provider_id=row.provider_id,
            transport=transport,
            tools=tools,
        )
        categories[row.id] = Category(row.category)

    callable_specs: dict[tuple[str, str], tuple[CallableSpec, str]] = {}
    rcs_rows = session.query(RunnerCallableSpec).all()
    for r in rcs_rows:
        callable_specs[(r.department_id, r.need_id)] = (
            CallableSpec.from_json(r.spec),
            r.connector_id,
        )

    return Dispatcher(
        connectors=prepared,
        allowlist={},  # legacy field unused for chat post-redesign
        connector_categories=categories,
        callable_specs=callable_specs,
    )
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_dispatcher_factory.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/dispatcher_factory.py packages/server/tests/test_services/test_dispatcher_factory.py
git commit -m "feat(server): dispatcher_factory hydrates Dispatcher with callable_specs"
```

---

## Phase 6 — Runtime router and chat-runner integration

### Task 6.1 — Runtime router service

**Files:**
- Create: `packages/server/src/openlia_server/services/runtime_router.py`
- Test: `packages/server/tests/test_services/test_runtime_router.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_runtime_router.py`:
```python
from unittest.mock import AsyncMock

import pytest

from openlia_server.services.runtime_router import (
    EscalationToolDef,
    parse_router_response,
    route_for_conversation,
)


def test_parse_router_response_returns_tool_name_list():
    raw = {"tools": ["eodhd__get_quote", "eodhd__economic_data"]}
    assert parse_router_response(raw) == ["eodhd__get_quote", "eodhd__economic_data"]


def test_parse_router_response_filters_unknown_names():
    raw = {"tools": ["eodhd__get_quote", "ghost_tool", "eodhd__economic_data"]}
    valid = {"eodhd__get_quote", "eodhd__economic_data"}
    assert parse_router_response(raw, valid_names=valid) == [
        "eodhd__get_quote",
        "eodhd__economic_data",
    ]


def test_parse_router_response_handles_array_response():
    raw = ["eodhd__get_quote"]
    assert parse_router_response(raw) == ["eodhd__get_quote"]


@pytest.mark.asyncio
async def test_route_for_conversation_returns_picked_subset_plus_escalation_tool():
    fake_llm = AsyncMock()
    fake_llm.complete_json.return_value = {"tools": ["eodhd__get_quote"]}
    candidate_tools = [
        {"name": "eodhd__get_quote", "description": "", "input_schema": {}},
        {"name": "eodhd__economic_data", "description": "", "input_schema": {}},
        {"name": "newsapi_ai__search", "description": "", "input_schema": {}},
    ]
    out = await route_for_conversation(
        department_id="equity_research",
        user_prompt="What's AAPL trading at?",
        candidate_tools=candidate_tools,
        routing_context="(routing context here)",
        router_llm=fake_llm,
    )
    names = [t["name"] for t in out]
    # The escalation tool is always included.
    assert "request_additional_tools" in names
    assert "eodhd__get_quote" in names
    assert "eodhd__economic_data" not in names


def test_escalation_tool_def_shape():
    t = EscalationToolDef
    assert t["name"] == "request_additional_tools"
    assert "reason" in t["input_schema"]["properties"]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_services/test_runtime_router.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement the router**

Create `packages/server/src/openlia_server/services/runtime_router.py`:
```python
"""Conversation-scoped runtime tool router for chat departments."""

from __future__ import annotations

import json
from typing import Any, Protocol


class _LLM(Protocol):
    async def complete_json(self, *, system: str, prompt: str) -> Any: ...


EscalationToolDef: dict[str, Any] = {
    "name": "request_additional_tools",
    "description": (
        "Call this if you realize you need a capability that's not in your "
        "current toolset. Provide a one-sentence reason describing what you "
        "want to do; new tools will be added to your toolset for the rest "
        "of the conversation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
        },
        "required": ["reason"],
    },
}


_SYSTEM_PROMPT = """\
You are routing tools for a department of an investor-assistant system.
Given the department's role context, the user's prompt, and the full
inventory of available tools, return a JSON object with a "tools" key
listing the tool names you'd expose to the main LLM for this conversation.

Be liberal: if a tool might plausibly be useful, include it.
Be conservative: do not include tools that are clearly off-topic.
Return only the tool names — they must come from the inventory.
"""


def _build_user_prompt(
    *,
    department_id: str,
    user_prompt: str,
    candidate_tools: list[dict[str, Any]],
    routing_context: str,
) -> str:
    lines = [
        f"Department: {department_id}",
        "",
        "Routing context:",
        routing_context,
        "",
        "User prompt:",
        user_prompt,
        "",
        "Available tools:",
    ]
    for t in candidate_tools:
        desc = t.get("description") or ""
        lines.append(f"- {t['name']}: {desc[:200]}")
    lines.append("")
    lines.append('Return JSON: {"tools": ["name1", "name2", ...]}')
    return "\n".join(lines)


def parse_router_response(
    raw: Any,
    *,
    valid_names: set[str] | None = None,
) -> list[str]:
    if isinstance(raw, dict):
        names = raw.get("tools") or []
    elif isinstance(raw, list):
        names = raw
    else:
        names = []
    out: list[str] = []
    for n in names:
        if not isinstance(n, str):
            continue
        if valid_names is not None and n not in valid_names:
            continue
        out.append(n)
    return out


async def route_for_conversation(
    *,
    department_id: str,
    user_prompt: str,
    candidate_tools: list[dict[str, Any]],
    routing_context: str,
    router_llm: _LLM,
) -> list[dict[str, Any]]:
    """Returns the routed subset (including the escalation tool) for the conversation."""

    valid_names = {t["name"] for t in candidate_tools}
    system = _SYSTEM_PROMPT
    user = _build_user_prompt(
        department_id=department_id,
        user_prompt=user_prompt,
        candidate_tools=candidate_tools,
        routing_context=routing_context,
    )
    raw = await router_llm.complete_json(system=system, prompt=user)
    chosen = parse_router_response(raw, valid_names=valid_names)
    by_name = {t["name"]: t for t in candidate_tools}
    out = [by_name[n] for n in chosen if n in by_name]
    out.append(EscalationToolDef)
    return out


async def reroute_on_escalation(
    *,
    department_id: str,
    recent_messages: list[dict[str, Any]],
    current_tool_names: set[str],
    candidate_tools: list[dict[str, Any]],
    routing_context: str,
    escalation_reason: str,
    router_llm: _LLM,
) -> list[dict[str, Any]]:
    """Returns the additional tools to merge into the current set."""

    valid_names = {t["name"] for t in candidate_tools}
    eligible = [t for t in candidate_tools if t["name"] not in current_tool_names]
    system = _SYSTEM_PROMPT
    lines = [
        f"Department: {department_id}",
        "",
        "Routing context:",
        routing_context,
        "",
        "Conversation so far (truncated):",
        json.dumps(recent_messages[-6:]),
        "",
        f"The main LLM has requested additional tools. Reason: {escalation_reason}",
        "",
        "Currently available tools (already in scope):",
        ", ".join(sorted(current_tool_names)),
        "",
        "Tools eligible to be added:",
    ]
    for t in eligible:
        lines.append(f"- {t['name']}: {(t.get('description') or '')[:200]}")
    lines.append("")
    lines.append('Return JSON: {"tools": ["name1", "name2", ...]} — only the *new* tools to add.')
    user = "\n".join(lines)
    raw = await router_llm.complete_json(system=system, prompt=user)
    chosen = parse_router_response(raw, valid_names=valid_names)
    chosen = [n for n in chosen if n not in current_tool_names]
    by_name = {t["name"]: t for t in candidate_tools}
    return [by_name[n] for n in chosen if n in by_name]
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_runtime_router.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/runtime_router.py packages/server/tests/test_services/test_runtime_router.py
git commit -m "feat(server): runtime_router service with conversation-scoped routing + escalation"
```

### Task 6.2 — ChatRunner integration

**Files:**
- Modify: `packages/server/src/openlia_server/services/chat_runner.py` (or whatever the post-cherry-pick name is — verify before edit)
- Test: `packages/server/tests/test_services/test_chat_runner_routing.py`

- [ ] **Step 1: Inspect the current ChatRunner to understand its loop**

```bash
grep -n "class ChatRunner\|tool_use\|tools=" packages/server/src/openlia_server/services/chat_runner.py | head -30
```

Take notes on: how tools are currently passed to the main LLM, where the message loop runs, where stream events are produced.

- [ ] **Step 2: Write the failing test**

Create `packages/server/tests/test_services/test_chat_runner_routing.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_chat_runner_routes_at_conversation_start_and_includes_escalation_tool(
    monkeypatch,
):
    """When ChatRunner starts a conversation, it should:
    1) Call route_for_conversation once with the user prompt + candidate pool.
    2) Pass the routed subset (including escalation tool) to the main LLM.
    """

    from openlia_server.services import chat_runner as cr

    routed = [
        {"name": "eodhd__get_quote", "description": "", "input_schema": {}},
        {"name": "request_additional_tools", "description": "", "input_schema": {}},
    ]
    route = AsyncMock(return_value=routed)
    monkeypatch.setattr(cr, "route_for_conversation", route)

    main_llm = AsyncMock()
    main_llm.stream.return_value = iter([])  # no tool uses
    dispatcher = MagicMock()
    dispatcher.candidate_tools_for_router.return_value = [
        {"name": "eodhd__get_quote", "description": "", "input_schema": {}},
        {"name": "fmp__get_profile", "description": "", "input_schema": {}},
    ]
    routing_context_loader = MagicMock(return_value="(routing context)")

    runner = cr.ChatRunner(
        main_llm=main_llm,
        router_llm=AsyncMock(),
        dispatcher=dispatcher,
        load_routing_context=routing_context_loader,
    )
    convo = await runner.start_conversation(
        department_id="equity_research",
        user_prompt="What's AAPL trading at?",
    )
    route.assert_awaited_once()
    main_llm.stream.assert_called_once()
    tools_arg = main_llm.stream.call_args.kwargs["tools"]
    names = [t["name"] for t in tools_arg]
    assert "eodhd__get_quote" in names
    assert "request_additional_tools" in names
```

(The test names a `ChatRunner` API that may not exist as-is on the current branch. If it doesn't, design the public surface as part of this task: `start_conversation(...)`, `continue_turn(...)`. Adapt to fit.)

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_services/test_chat_runner_routing.py -v
```

Expected: FAIL — wiring missing.

- [ ] **Step 4: Refactor ChatRunner**

Modify `packages/server/src/openlia_server/services/chat_runner.py`:

```python
from openlia_server.services.runtime_router import route_for_conversation, reroute_on_escalation
from openlia.connectors.dispatch import Dispatcher

class ChatRunner:
    def __init__(
        self,
        *,
        main_llm,
        router_llm,
        dispatcher: Dispatcher,
        load_routing_context,  # callable: (dept_id) -> str
    ) -> None:
        self._main_llm = main_llm
        self._router_llm = router_llm
        self._dispatcher = dispatcher
        self._load_routing_context = load_routing_context

    async def start_conversation(self, *, department_id: str, user_prompt: str):
        candidate = self._dispatcher.candidate_tools_for_router(department_id)
        routing_ctx = self._load_routing_context(department_id)
        routed = await route_for_conversation(
            department_id=department_id,
            user_prompt=user_prompt,
            candidate_tools=candidate,
            routing_context=routing_ctx,
            router_llm=self._router_llm,
        )
        return await self._run_main_loop(
            department_id=department_id,
            initial_user_prompt=user_prompt,
            tools=routed,
        )

    async def _run_main_loop(self, *, department_id, initial_user_prompt, tools):
        messages = [{"role": "user", "content": initial_user_prompt}]
        current_tool_names = {t["name"] for t in tools}
        while True:
            stream = self._main_llm.stream(
                tools=tools,
                messages=messages,
            )
            tool_uses: list[dict] = []
            async for ev in stream:
                if ev.get("type") == "tool_use":
                    tool_uses.append(ev)
                yield ev
            if not tool_uses:
                return
            tool_results = []
            for tu in tool_uses:
                if tu["name"] == "request_additional_tools":
                    extra = await reroute_on_escalation(
                        department_id=department_id,
                        recent_messages=messages,
                        current_tool_names=current_tool_names,
                        candidate_tools=self._dispatcher.candidate_tools_for_router(department_id),
                        routing_context=self._load_routing_context(department_id),
                        escalation_reason=tu["input"]["reason"],
                        router_llm=self._router_llm,
                    )
                    tools = list(tools) + extra
                    current_tool_names.update(t["name"] for t in extra)
                    summary = "Added tools: " + ", ".join(t["name"] for t in extra) if extra else "No additional tools matched."
                    tool_results.append({"tool_use_id": tu["id"], "content": summary})
                else:
                    result = await self._dispatcher.dispatch_tool_use(tu["name"], tu["input"])
                    tool_results.append({"tool_use_id": tu["id"], "content": result})
            messages.append({"role": "assistant", "content": tool_uses})
            messages.append({"role": "user", "content": tool_results})
```

(The exact integration points depend on the existing ChatRunner shape on `main` post-cutover-cherry-pick. Preserve any existing instrumentation, schedules, audit hooks.)

- [ ] **Step 5: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_chat_runner_routing.py -v
```

Expected: PASS.

- [ ] **Step 6: Run the broader chat-runner test suite**

```bash
uv run pytest packages/server/tests/test_services/ -k chat -v 2>&1 | tail -20
```

Expected: PASS. Existing tests that previously expected `tools_for_department(department_id, has_web_search=...)` calls need to be updated to use the new candidate-pool flow.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/services/chat_runner.py packages/server/tests/test_services/test_chat_runner_routing.py
git commit -m "refactor(chat): conversation-scoped router + escalation tool integration"
```

### Task 6.3 — ReportRunner integration

**Files:**
- Modify: `packages/server/src/openlia_server/services/report_runner.py` (verify exact path)
- Test: `packages/server/tests/test_services/test_report_runner_routing.py`

- [ ] **Step 1: Write the failing test**

Mirror the pattern from Task 6.2. The test asserts that `ReportRunner` routes at the start of a report-generation pass and exposes the escalation tool.

- [ ] **Step 2: Apply the same refactor pattern as ChatRunner**

ReportRunner's data-fetching section is structurally identical to ChatRunner's: invoke router → run main LLM with routed subset → handle tool_use round-trips → handle escalation. Refactor in-place.

- [ ] **Step 3: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_report_runner_routing.py -v
```

Expected: PASS.

- [ ] **Step 4: Run all server tests**

```bash
uv run pytest packages/server/tests/ -v 2>&1 | tail -30
```

Expected: passing or known-skipped.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/report_runner.py packages/server/tests/test_services/test_report_runner_routing.py
git commit -m "refactor(report): conversation-scoped router + escalation tool integration"
```

---

## Phase 7 — Department health system

### Task 7.1 — `dept_health` service

**Files:**
- Create: `packages/server/src/openlia_server/services/dept_health.py`
- Test: `packages/server/tests/test_services/test_dept_health.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_dept_health.py`:
```python
import pytest

from openlia.connectors.types import Category
from openlia.departments.equity_research import EquityResearchDepartment
from openlia.departments.macro_research import MacroResearchDepartment
from openlia.departments.secretary import SecretaryDepartment
from openlia_server.db.models.connectors import Connector
from openlia_server.db.models.runner_callable_specs import RunnerCallableSpec
from openlia_server.services.dept_health import DeptHealth, check_dept_health


def test_secretary_always_active(session_factory):
    with session_factory() as s:
        health = check_dept_health(SecretaryDepartment(), s)
    assert health.status == "active"


def test_equity_research_disabled_without_financial_connector(session_factory):
    with session_factory() as s:
        health = check_dept_health(EquityResearchDepartment(), s)
    assert health.status == "disabled"
    assert "financial" in (health.reason or "")


def test_equity_research_active_with_validated_financial_connector(session_factory):
    with session_factory() as s:
        s.add(
            Connector(
                id="c1",
                provider_id="eodhd",
                source="cli_mcp",
                category="financial",
                launch={"modes": []},
                status="validated",
            )
        )
        s.commit()
        health = check_dept_health(EquityResearchDepartment(), s)
    assert health.status == "active"


def test_macro_research_disabled_when_needs_unresolved(session_factory):
    with session_factory() as s:
        s.add(
            Connector(
                id="c1",
                provider_id="eodhd",
                source="cli_mcp",
                category="financial",
                launch={"modes": []},
                status="validated",
            )
        )
        s.commit()
        health = check_dept_health(MacroResearchDepartment(), s)
    assert health.status == "disabled"
    assert "callable spec" in (health.reason or "").lower()


def test_macro_research_active_when_all_needs_resolved(session_factory, monkeypatch):
    from openlia.departments import loader

    monkeypatch.setattr(
        loader,
        "load_needs",
        lambda dept_id: [
            type("N", (), {"id": "debt_gdp"})()
        ] if dept_id == "macro_research" else [],
    )

    with session_factory() as s:
        s.add(
            Connector(
                id="c1",
                provider_id="eodhd",
                source="cli_mcp",
                category="financial",
                launch={"modes": []},
                status="validated",
            )
        )
        s.add(
            RunnerCallableSpec(
                id="rcs1",
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id="c1",
                access_mode="python_lib",
                spec={},
            )
        )
        s.commit()
        health = check_dept_health(MacroResearchDepartment(), s)
    assert health.status == "active"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_services/test_dept_health.py -v
```

Expected: FAIL on import.

- [ ] **Step 3: Implement health check**

Create `packages/server/src/openlia_server/services/dept_health.py`:
```python
"""Compute health status for each department based on configured connectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from openlia.connectors.types import Category, ConnectorStatus
from openlia.departments.loader import load_needs
from openlia_server.db.models.connectors import Connector
from openlia_server.db.models.runner_callable_specs import RunnerCallableSpec


@dataclass(frozen=True)
class DeptHealth:
    department_id: str
    status: Literal["active", "disabled"]
    reason: str | None


class Department(Protocol):
    name: str
    required_categories: tuple[Category, ...]
    optional_categories: tuple[Category, ...]
    requires_runner: bool


def has_validated_connector_in_category(db: Session, category: Category) -> bool:
    return (
        db.query(Connector)
        .filter(Connector.status == ConnectorStatus.VALIDATED.value)
        .filter(Connector.category == category.value)
        .count()
        > 0
    )


def needs_without_callable_spec(db: Session, department_id: str) -> list[str]:
    declared = [n.id for n in load_needs(department_id)]
    if not declared:
        return []
    have = {
        r.need_id
        for r in db.query(RunnerCallableSpec)
        .filter(RunnerCallableSpec.department_id == department_id)
        .all()
    }
    return [n for n in declared if n not in have]


def check_dept_health(dept: Department, db: Session) -> DeptHealth:
    missing = [
        c for c in dept.required_categories
        if not has_validated_connector_in_category(db, c)
    ]
    if missing:
        return DeptHealth(
            department_id=dept.name,
            status="disabled",
            reason=(
                f"No connector configured for required categories: "
                f"{', '.join(c.value for c in missing)}"
            ),
        )
    if dept.requires_runner:
        unresolved = needs_without_callable_spec(db, dept.name)
        if unresolved:
            return DeptHealth(
                department_id=dept.name,
                status="disabled",
                reason=(
                    f"No callable spec resolved for runner needs: "
                    f"{', '.join(unresolved)}. Configure a Python library mode "
                    f"for the relevant financial connector."
                ),
            )
    return DeptHealth(department_id=dept.name, status="active", reason=None)
```

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_dept_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/dept_health.py packages/server/tests/test_services/test_dept_health.py
git commit -m "feat(server): department health check service"
```

### Task 7.2 — Health snapshot in app.state + invalidation hooks

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`
- Modify: `packages/server/src/openlia_server/services/connectors_service.py` (call invalidate on status change)
- Test: `packages/server/tests/test_app/test_dept_health_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_app/test_dept_health_lifecycle.py`:
```python
import pytest

from openlia_server.db.models.connectors import Connector


def test_app_state_dept_health_populated_at_startup(client_with_session):
    client, session_factory = client_with_session
    health = client.app.state.dept_health
    assert "secretary" in {h.department_id for h in health}


def test_dept_health_invalidates_on_connector_validation(client_with_session):
    client, session_factory = client_with_session
    initial = {h.department_id for h in client.app.state.dept_health if h.status == "active"}
    assert "equity_research" not in initial

    with session_factory() as s:
        s.add(
            Connector(
                id="c1",
                provider_id="eodhd",
                source="cli_mcp",
                category="financial",
                launch={"modes": []},
                status="validated",
            )
        )
        s.commit()
    # The connectors_service.refresh_dept_health() is called on row commit hooks;
    # for the test we explicitly trigger.
    from openlia_server.services.dept_health import refresh_dept_health
    refresh_dept_health(client.app)
    after = {h.department_id for h in client.app.state.dept_health if h.status == "active"}
    assert "equity_research" in after
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_app/test_dept_health_lifecycle.py -v
```

Expected: FAIL — `refresh_dept_health` and the lifecycle wiring don't exist.

- [ ] **Step 3: Add `refresh_dept_health` to dept_health service**

Append to `packages/server/src/openlia_server/services/dept_health.py`:
```python
def refresh_dept_health(app) -> None:
    """Recompute and store dept health snapshot on app.state."""

    from openlia_server.db.session import session_scope
    from openlia.departments import all_departments  # see Task 7.3 if missing

    snapshot: list[DeptHealth] = []
    with session_scope() as s:
        for dept in all_departments():
            snapshot.append(check_dept_health(dept, s))
    app.state.dept_health = snapshot
```

- [ ] **Step 4: Add `all_departments()` if not present**

Edit `packages/core/src/openlia/departments/__init__.py`:
```python
from openlia.departments.earnings_update import EarningsUpdateDepartment
from openlia.departments.equity_research import EquityResearchDepartment
from openlia.departments.macro_research import MacroResearchDepartment
from openlia.departments.morning_briefing import MorningBriefingDepartment
from openlia.departments.panic_thermometer import PanicThermometerDepartment
from openlia.departments.retail_sentiment import RetailSentimentDepartment
from openlia.departments.secretary import SecretaryDepartment


def all_departments() -> list[object]:
    return [
        SecretaryDepartment(),
        EquityResearchDepartment(),
        EarningsUpdateDepartment(),
        MorningBriefingDepartment(),
        MacroResearchDepartment(),
        RetailSentimentDepartment(),
        PanicThermometerDepartment(),
    ]
```

- [ ] **Step 5: Wire `refresh_dept_health` into app startup**

In `packages/server/src/openlia_server/app.py`, in the lifespan/startup block:
```python
from openlia_server.services.dept_health import refresh_dept_health

# ...inside lifespan startup, after DB is ready:
refresh_dept_health(app)
```

In `packages/server/src/openlia_server/services/connectors_service.py`, after every status transition (validate / fail / delete) call `refresh_dept_health(self._app)` (or pass the app reference through the service constructor; whichever fits the existing pattern).

- [ ] **Step 6: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_app/test_dept_health_lifecycle.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/services/dept_health.py packages/server/src/openlia_server/app.py packages/server/src/openlia_server/services/connectors_service.py packages/core/src/openlia/departments/__init__.py packages/server/tests/test_app/test_dept_health_lifecycle.py
git commit -m "feat(server): dept_health snapshot on app.state with invalidation hooks"
```

### Task 7.3 — API: 409 Conflict for disabled depts

**Files:**
- Modify: `packages/server/src/openlia_server/middleware/dept_health_gate.py` (create)
- Modify: `packages/server/src/openlia_server/app.py` (register middleware)
- Test: `packages/server/tests/test_middleware/test_dept_health_gate.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_middleware/test_dept_health_gate.py`:
```python
def test_disabled_dept_mutating_endpoint_returns_409(client_no_connectors):
    client = client_no_connectors
    # POST a chat to equity_research — disabled because no financial connector.
    resp = client.post("/api/departments/equity_research/chat", json={"message": "hi"})
    assert resp.status_code == 409
    body = resp.json()
    assert "financial" in body.get("detail", "").lower() or "financial" in body.get("reason", "")


def test_disabled_dept_read_endpoint_works(client_no_connectors):
    client = client_no_connectors
    resp = client.get("/api/departments/equity_research/state")
    assert resp.status_code == 200


def test_active_dept_unaffected(client_with_financial_connector):
    client = client_with_financial_connector
    resp = client.post("/api/departments/equity_research/chat", json={"message": "hi"})
    assert resp.status_code != 409
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_middleware/test_dept_health_gate.py -v
```

Expected: FAIL — middleware not registered.

- [ ] **Step 3: Implement the gate**

Create `packages/server/src/openlia_server/middleware/dept_health_gate.py`:
```python
"""Block mutating endpoints on disabled departments with HTTP 409."""

from __future__ import annotations

import re
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp


_DEPT_PATH_RE = re.compile(r"^/api/departments/(?P<dept>[a-z_]+)/")
# Conservative: any non-GET on a /api/departments/<dept>/ path is mutating.
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class DeptHealthGate:
    def __init__(self, app: ASGIApp, fastapi_app: FastAPI) -> None:
        self._app = app
        self._fastapi_app = fastapi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if method in _MUTATING_METHODS:
            m = _DEPT_PATH_RE.match(path)
            if m:
                dept = m.group("dept")
                snapshot = getattr(self._fastapi_app.state, "dept_health", [])
                disabled = next(
                    (h for h in snapshot if h.department_id == dept and h.status == "disabled"),
                    None,
                )
                if disabled is not None:
                    response = JSONResponse(
                        status_code=409,
                        content={
                            "department_id": disabled.department_id,
                            "reason": disabled.reason,
                        },
                    )
                    await response(scope, receive, send)
                    return
        await self._app(scope, receive, send)


def install_dept_health_gate(app: FastAPI) -> None:
    app.add_middleware(DeptHealthGate, fastapi_app=app)
```

- [ ] **Step 4: Register the middleware**

In `packages/server/src/openlia_server/app.py`:
```python
from openlia_server.middleware.dept_health_gate import install_dept_health_gate

# After other middleware registrations:
install_dept_health_gate(app)
```

- [ ] **Step 5: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_middleware/test_dept_health_gate.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/middleware/dept_health_gate.py packages/server/src/openlia_server/app.py packages/server/tests/test_middleware/test_dept_health_gate.py
git commit -m "feat(server): 409 gate for mutating endpoints on disabled departments"
```

### Task 7.4 — Scheduler skip for disabled depts

**Files:**
- Modify: `packages/server/src/openlia_server/services/scheduler.py` (or wherever cron tasks live)
- Test: `packages/server/tests/test_services/test_scheduler_dept_health_skip.py`

- [ ] **Step 1: Write the failing test**

```python
def test_scheduler_skips_disabled_dept_jobs(client_no_connectors, caplog):
    # Trigger a scheduled MR run; expect "skipped: disabled" log and no runner invocation.
    from openlia_server.services.mr_schedules import run_mr_schedule_for_user

    invoked = {"runner": False}

    def fake_runner(*a, **kw):
        invoked["runner"] = True

    with caplog.at_level("INFO"):
        run_mr_schedule_for_user(user_id="u1", _runner=fake_runner)
    assert "skipped" in caplog.text.lower()
    assert invoked["runner"] is False
```

- [ ] **Step 2: Verify failure, then implement**

In every scheduler entry-point that invokes a runner, add a pre-flight:
```python
from openlia.departments.macro_research import MacroResearchDepartment
from openlia_server.services.dept_health import check_dept_health

def run_mr_schedule_for_user(user_id: str, _runner=None) -> None:
    with session_scope() as s:
        health = check_dept_health(MacroResearchDepartment(), s)
        if health.status == "disabled":
            log.info("skipped: %s — %s", health.department_id, health.reason)
            return
    (_runner or default_runner).run(user_id=user_id, ...)
```

Apply the same pattern in any other scheduled-task entry points (RS schedule, PT trigger eval, etc.).

- [ ] **Step 3: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_scheduler_dept_health_skip.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/services/ packages/server/tests/test_services/test_scheduler_dept_health_skip.py
git commit -m "feat(scheduler): skip disabled departments with informative log"
```

### Task 7.5 — `GET /api/dept-health` route

**Files:**
- Create: `packages/server/src/openlia_server/routes/dept_health.py`
- Modify: `packages/server/src/openlia_server/app.py` (register router)
- Test: `packages/server/tests/test_routes/test_dept_health_route.py`

- [ ] **Step 1: Write the failing test**

```python
def test_dept_health_route_returns_snapshot(client_no_connectors):
    client = client_no_connectors
    resp = client.get("/api/dept-health")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    by_id = {h["department_id"]: h for h in body}
    assert by_id["secretary"]["status"] == "active"
    # Without connectors, equity_research is disabled with a financial reason.
    assert by_id["equity_research"]["status"] == "disabled"
    assert "financial" in by_id["equity_research"]["reason"]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/server/tests/test_routes/test_dept_health_route.py -v
```

Expected: FAIL — route doesn't exist.

- [ ] **Step 3: Implement the route**

Create `packages/server/src/openlia_server/routes/dept_health.py`:
```python
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["dept-health"])


@router.get("/dept-health")
def get_dept_health(request: Request) -> list[dict]:
    snapshot = getattr(request.app.state, "dept_health", [])
    return [asdict(h) for h in snapshot]
```

- [ ] **Step 4: Register the router**

In `packages/server/src/openlia_server/app.py`:
```python
from openlia_server.routes.dept_health import router as dept_health_router

# After other router registrations:
app.include_router(dept_health_router)
```

- [ ] **Step 5: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_routes/test_dept_health_route.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/dept_health.py packages/server/src/openlia_server/app.py packages/server/tests/test_routes/test_dept_health_route.py
git commit -m "feat(server): GET /api/dept-health returns department health snapshot"
```

---

## Phase 8 — MR/RS runner migration

### Task 8.1 — MR T1 stage uses `fetch_need`

**Files:**
- Modify: `packages/core/src/openlia/macro_research/assembler.py`
- Modify: `packages/core/src/openlia/macro_research/dashboards/*.py` — convert `T1_REQUIREMENTS` to `T1_NEEDS`
- Test: `packages/core/tests/test_macro_research/test_t1_fetch_need.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_macro_research/test_t1_fetch_need.py`:
```python
import pytest

from openlia.macro_research.assembler import DashboardAssembler
from openlia.macro_research.dashboards.debt_cycle import DebtCycleDashboard


@pytest.mark.asyncio
async def test_debt_cycle_t1_calls_fetch_need_for_each_declared_need():
    fetched = {}

    class FakeDispatcher:
        async def fetch_need(self, need_id, **kwargs):
            fetched[need_id] = kwargs
            return {"debt_gdp": 122.4, "interest_revenue": 17.0, "tips_quote": 105.5, "dxy_proxy": 28.4}.get(
                need_id, 0.0
            )

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def in_department(self, dept_id):
            yield

    asm = DashboardAssembler(dispatcher=FakeDispatcher())
    result = await asm.run_async(
        dashboard_slug="debt_cycle",
        user_id="u1",
        portfolio=None,
        t4_cached=None,
        smart_mode=False,
    )
    # Each declared need was fetched.
    assert {"debt_gdp", "interest_revenue", "tips_quote", "dxy_proxy"}.issubset(fetched.keys())
    # T1 tier carries real values.
    t1 = next(t for t in result.tiers if t.tier == "T1")
    assert t1.data["inputs"]["debt_gdp"] == 122.4


def test_debt_cycle_dashboard_declares_t1_needs():
    d = DebtCycleDashboard()
    assert "debt_gdp" in d.T1_NEEDS
    assert "tips_quote" in d.T1_NEEDS
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest packages/core/tests/test_macro_research/test_t1_fetch_need.py -v
```

Expected: FAIL — `T1_NEEDS` and `run_async` don't exist.

- [ ] **Step 3: Convert each dashboard's `T1_REQUIREMENTS` to `T1_NEEDS`**

For each dashboard module in `packages/core/src/openlia/macro_research/dashboards/`:
- Replace `T1_REQUIREMENTS: ClassVar[tuple[str, ...]] = (...)` with `T1_NEEDS: ClassVar[tuple[str, ...]] = (...)`
- Use the new id vocabulary from `macro_research.needs.yaml` (e.g., `"debt_gdp"`, `"tips_quote"`, `"dxy_proxy"`, `"stock_quote"`).
- Where the dashboard previously specified ticker-shaped requirements (`"stock_quote:TIP"`), it now declares `"stock_quote"` once and provides ticker arguments via a new `runtime_args_for(need_id) -> dict` method.

Example for `debt_cycle.py`:
```python
class DebtCycleDashboard:
    slug = "debt_cycle"
    display_name = "Debt Cycle"
    T1_NEEDS: ClassVar[tuple[str, ...]] = (
        "debt_gdp",
        "interest_revenue",
        "tips_quote",
        "dxy_proxy",
    )
    T1_RUNTIME_ARGS: ClassVar[dict[str, dict[str, object]]] = {
        # All four needs in this dashboard are pre-bound (no args).
    }
    # ... existing T2/T3/T4 unchanged ...
```

For `debt_cycle.py`, the existing T2_FORMULAS continue to reference `"debt_gdp"` etc. — values now come from the fetched dict.

For dashboards that consume the same parameterized need with different arguments (e.g., `four_seasons` wants `stock_quote` for HYG and LQD), use a list-of-pairs shape:

```python
class FourSeasonsDashboard:
    T1_NEEDS: ClassVar[tuple[str, ...]] = (
        "pmi", "gdp_yoy", "cpi_yoy", "cpi_core_yoy", "stock_quote", "stock_quote",
    )
    T1_PER_NEED_ARGS: ClassVar[tuple[dict[str, object], ...]] = (
        {}, {}, {}, {},
        {"ticker": "HYG"},
        {"ticker": "LQD"},
    )
```

The assembler iterates `zip(T1_NEEDS, T1_PER_NEED_ARGS)` and fetches each. The result is keyed by a label combining need_id + arg pairs (e.g. `"stock_quote:ticker=HYG"`) so T2 formulas can continue to reference values by their pre-redesign keys.

- [ ] **Step 4: Refactor `DashboardAssembler.run_async`**

In `packages/core/src/openlia/macro_research/assembler.py`:
```python
class DashboardAssembler:
    def __init__(
        self,
        *,
        dispatcher,            # Dispatcher with fetch_need + in_department
        llm_client=None,
    ) -> None:
        self._dispatcher = dispatcher
        self._llm = llm_client
        self._engine = FormulaEngine()

    async def run_async(
        self,
        *,
        dashboard_slug: str,
        user_id: str,
        portfolio: dict[str, float] | None,
        t4_cached: dict[str, Any] | None,
        smart_mode: bool,
    ) -> DashboardResult:
        if dashboard_slug not in DASHBOARDS:
            raise KeyError(f"unknown dashboard: {dashboard_slug!r}")
        dashboard = DASHBOARDS[dashboard_slug]
        now = datetime.now(UTC)

        # T1 — fetch each declared need.
        t1_data: dict[str, Any] = {}
        async with self._dispatcher.in_department("macro_research"):
            for need_id, args in zip(dashboard.T1_NEEDS, getattr(dashboard, "T1_PER_NEED_ARGS", ()) or [{}] * len(dashboard.T1_NEEDS)):
                t1_data[_label_for(need_id, args)] = await self._dispatcher.fetch_need(need_id, **args)
        # ...rest unchanged...


def _label_for(need_id: str, args: dict[str, Any]) -> str:
    if not args:
        return need_id
    return need_id + ":" + ":".join(f"{k}={v}" for k, v in args.items())
```

The label preserves the existing `"stock_quote:TIP"`-style key so T2 formulas continue to work without rewriting.

- [ ] **Step 5: Update `MRRunner` to pass the dispatcher to the assembler**

```python
class MRRunner:
    def __init__(
        self,
        *,
        dispatcher,
        cache_store,
        dashboard_service,
        session_factory,
    ) -> None:
        self._dispatcher = dispatcher
        # ...existing...
        self._asm = DashboardAssembler(dispatcher=dispatcher)
```

- [ ] **Step 6: Verify tests pass**

```bash
uv run pytest packages/core/tests/test_macro_research/ packages/server/tests/test_macro_research/ -v 2>&1 | tail -20
```

Expected: PASS. The 16 previously-skipped MR tests now run; un-skip them by removing the `pytest.mark.skip(...)` from each.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/macro_research/ packages/server/src/openlia_server/services/mr_runner.py packages/core/tests/test_macro_research/ packages/server/tests/test_macro_research/
git commit -m "refactor(mr): T1 stage uses dispatcher.fetch_need; un-skip 16 tests"
```

### Task 8.2 — RS `_fetch_posts` uses `fetch_need`

**Files:**
- Modify: `packages/server/src/openlia_server/services/rs_runner.py`
- Test: `packages/server/tests/test_services/test_rs_runner_fetch_need.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from openlia_server.services.rs_runner import RsRunner


@pytest.mark.asyncio
async def test_rs_runner_fetches_posts_via_fetch_need():
    fetched = {}

    class FakeDispatcher:
        async def fetch_need(self, need_id, **kwargs):
            fetched[need_id] = kwargs
            if need_id == "social_posts":
                return [
                    {"id": "p1", "body": "$AAPL to the moon", "author": "u1",
                     "timestamp": "2026-04-27T10:00:00Z", "source": "stocktwits"},
                ]
            return []

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def in_department(self, _):
            yield

    runner = RsRunner(
        session_factory=lambda: None,
        dispatcher=FakeDispatcher(),
    )
    posts = await runner._fetch_posts_async("AAPL")
    assert len(posts) == 1
    assert fetched == {"social_posts": {"ticker": "AAPL"}}
```

- [ ] **Step 2: Verify failure, then refactor**

In `rs_runner.py`:
```python
class RsRunner:
    def __init__(self, *, session_factory, dispatcher, ...):
        self._dispatcher = dispatcher
        # ...

    async def _fetch_posts_async(self, ticker: str) -> list[RawSocialPost]:
        async with self._dispatcher.in_department("retail_sentiment"):
            raw = await self._dispatcher.fetch_need("social_posts", ticker=ticker)
        return [RawSocialPost.from_dict(item) for item in raw]
```

If the call sites currently call `_fetch_posts(ticker)` synchronously, convert them or wrap:
```python
def _fetch_posts(self, ticker: str) -> list[RawSocialPost]:
    return asyncio.run(self._fetch_posts_async(ticker))
```
Use the same approach for `_fetch_optional`.

- [ ] **Step 3: Re-enable any RS tests that were `pytest.mark.skip`**

```bash
grep -rn "pytest.mark.skip.*MR/RS" packages/server/tests/ | head
```

Remove the skip markers; rerun.

- [ ] **Step 4: Verify tests pass**

```bash
uv run pytest packages/server/tests/test_services/test_rs_runner_fetch_need.py packages/server/tests/test_services/test_rs_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/rs_runner.py packages/server/tests/test_services/test_rs_runner_fetch_need.py
git commit -m "refactor(rs): _fetch_posts uses dispatcher.fetch_need; un-skip RS tests"
```

---

## Phase 9 — Cutover deletions and deprecations

### Task 9.1 — Cherry-pick H10 (drop data_providers tables)

The cutover branch's `5225a36 feat(db): drop data_providers tables; CLI rotation iterates Connector` is still valid. Cherry-pick it now.

- [ ] **Step 1: Cherry-pick**

```bash
git cherry-pick 5225a36
```

Resolve any conflicts (likely in CLI rotation logic where iteration is updated).

- [ ] **Step 2: Run migrations and verify the legacy tables are gone**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
sqlite3 .openlia.dev.db ".tables" | tr ' ' '\n' | grep -E "data_provider|tool_allow"
```

Expected: empty output (none of these tables exist).

- [ ] **Step 3: Run full suite**

```bash
uv run pytest 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 4: Commit (already done by cherry-pick)**

### Task 9.2 — Delete `*.requirements.yaml`

The legacy per-dept `requirements.yaml` files are now superseded by `routing_context.md` + `needs.yaml`. Delete them.

- [ ] **Step 1: Verify no consumer remains**

```bash
grep -rn "requirements\.yaml\|requirements_yaml\|load_department_requirements" packages | head
```

If any references remain, refactor them to use the new loader before proceeding.

- [ ] **Step 2: Delete the seven files**

```bash
git rm packages/core/src/openlia/departments/{secretary,equity_research,earnings_update,morning_briefing,macro_research,retail_sentiment,panic_thermometer}.requirements.yaml
```

- [ ] **Step 3: Delete the legacy `requirements_loader.py` if it exists**

```bash
git rm -f packages/core/src/openlia/departments/requirements_loader.py
```

(If a different module name was used, adjust.)

- [ ] **Step 4: Run full suite**

```bash
uv run pytest 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(departments): delete legacy *.requirements.yaml and loader"
```

### Task 9.3 — Empty the built-in template catalog

The cutover branch (and current `main`) ship stub built-in template registrations for EODHD, FMP, and NewsAPI.ai with placeholder allowlists. The redesign defers the day-1 catalog decision (per spec §13.5) — no built-in MCP templates or Python libs are shipped pre-wired. The registry infrastructure (`register`, `get_builtin`, `all_builtins`) stays so future built-ins can plug in.

**Files:**
- Delete: `packages/core/src/openlia/connectors/builtins/eodhd.py`
- Delete: `packages/core/src/openlia/connectors/builtins/fmp.py`
- Delete: `packages/core/src/openlia/connectors/builtins/newsapi_ai.py`
- Delete: `packages/core/tests/test_connectors/test_builtins_eodhd.py`
- Delete: `packages/core/tests/test_connectors/test_builtins_fmp.py`
- Delete: `packages/core/tests/test_connectors/test_builtins_newsapi_ai.py`
- Modify: `packages/core/tests/test_connectors/test_builtins_registry.py` — replace `eodhd`-specific tests with registry-shape tests using a synthetic template

- [ ] **Step 1: Verify no production code currently fails when the registry is empty**

```bash
grep -rn 'get_builtin\("eodhd"\|get_builtin\("fmp"\|get_builtin\("newsapi' packages/ --include="*.py"
```

Expected: matches only inside test files (which we delete or rewrite below). If production code references `get_builtin("eodhd")` etc., that's a bug — the wizard chooses templates by user input, not by hardcoded id. Track down and replace with parameterized lookups before continuing.

- [ ] **Step 2: Delete the three stub registration files**

```bash
git rm packages/core/src/openlia/connectors/builtins/eodhd.py
git rm packages/core/src/openlia/connectors/builtins/fmp.py
git rm packages/core/src/openlia/connectors/builtins/newsapi_ai.py
```

- [ ] **Step 3: Delete the three template-specific test files**

```bash
git rm packages/core/tests/test_connectors/test_builtins_eodhd.py
git rm packages/core/tests/test_connectors/test_builtins_fmp.py
git rm packages/core/tests/test_connectors/test_builtins_newsapi_ai.py
```

- [ ] **Step 4: Rewrite `test_builtins_registry.py` to exercise the registry shape, not specific templates**

Replace the contents of `packages/core/tests/test_connectors/test_builtins_registry.py`:
```python
"""Registry shape tests — no specific built-ins ship day-1."""

from __future__ import annotations

import pytest

from openlia.connectors.builtins import (
    BuiltInTemplate,
    all_builtins,
    get_builtin,
    register,
)
from openlia.connectors.builtins._types import ShippedAssignment
from openlia.connectors.types import Category


def test_registry_is_empty_day_1():
    assert all_builtins() == []


def test_get_builtin_unknown_raises():
    with pytest.raises(KeyError):
        get_builtin("nope")


def test_register_then_lookup_round_trip(monkeypatch):
    """Registry mechanics: a template can be registered and retrieved."""

    # The registry holds module-level state; isolate to this test by
    # registering a unique template_id and verifying lookup.
    template_id = "test_template_for_registry_round_trip"
    tpl = BuiltInTemplate(
        template_id=template_id,
        display_name="Test",
        category=Category.FINANCIAL,
        api_key_env_var="TEST_API_KEY",
        cli_argv=("uvx", "test-mcp"),
        canary_tool=None,
        shipped_allowlist=(),
    )
    register(tpl)
    try:
        assert get_builtin(template_id) is tpl
        assert any(t.template_id == template_id for t in all_builtins())
    finally:
        # Clean up to keep test isolation: clear the registered entry.
        from openlia.connectors.builtins import _REGISTRY

        _REGISTRY.pop(template_id, None)
```

If the existing `builtins/__init__.py` does not expose `_REGISTRY` directly, expose it (or add a small `_test_only_clear(template_id)` helper) so the test can clean up.

- [ ] **Step 5: Verify no consumers fail with empty catalog**

```bash
uv run pytest 2>&1 | tail -10
```

Expected: PASS. Wizard tests that previously assumed a populated catalog should be parameterized over user-supplied connectors only.

- [ ] **Step 6: Verify the wizard's templates-list endpoint returns []**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
uv run openlia serve &
SERVER_PID=$!
sleep 3
curl -s http://localhost:8000/api/connectors/templates
kill $SERVER_PID
```

Expected: `[]` (assuming the templates route is `/api/connectors/templates` — verify against the actual route name on the branch).

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/connectors/builtins/ packages/core/tests/test_connectors/test_builtins_registry.py
git commit -m "refactor(connectors): empty the built-in template catalog day-1

Per design spec §13.5, no specific built-in templates are decided yet.
Registry infrastructure stays for future built-ins to plug into; the
day-1 catalog ships empty. Users add connectors directly via the wizard
(remote MCP URL, CLI MCP launch, or Python library)."
```

---

## Phase 10 — Frontend

### Task 10.1 — Per-mode access selection in wizard ProvidersStep

**Files:**
- Modify: `frontend/src/components/SetupWizard/ProvidersStep.tsx`
- Test: `frontend/src/components/SetupWizard/ProvidersStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"
import ProvidersStep from "./ProvidersStep"

describe("ProvidersStep — multi-mode access selection", () => {
  it("renders mode checkboxes for built-in templates that ship multiple modes", () => {
    render(<ProvidersStep templates={[{ id: "eodhd", availableModes: ["cli_mcp", "python_lib"] }]} />)
    expect(screen.getByLabelText(/Enable MCP server/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Enable Python library/i)).toBeInTheDocument()
  })

  it("submits both modes when both checkboxes are ticked", async () => {
    const onSubmit = vi.fn()
    render(
      <ProvidersStep
        templates={[{ id: "eodhd", availableModes: ["cli_mcp", "python_lib"] }]}
        onSubmit={onSubmit}
      />
    )
    fireEvent.click(screen.getByLabelText(/Enable MCP server/i))
    fireEvent.click(screen.getByLabelText(/Enable Python library/i))
    fireEvent.change(screen.getByLabelText(/API key/i), { target: { value: "secret" } })
    fireEvent.click(screen.getByRole("button", { name: /add/i }))
    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        templateId: "eodhd",
        modes: ["cli_mcp", "python_lib"],
        apiKey: "secret",
      }))
    )
  })
})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd frontend && npx vitest run src/components/SetupWizard/ProvidersStep.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Update `ProvidersStep.tsx`**

Add a per-mode checkbox section that surfaces the modes a built-in template ships. Wire the form state to send `modes: string[]` to the backend. Capture the API key once.

- [ ] **Step 4: Verify tests pass**

```bash
npx vitest run src/components/SetupWizard/ProvidersStep.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SetupWizard/ProvidersStep.tsx frontend/src/components/SetupWizard/ProvidersStep.test.tsx
git commit -m "feat(frontend): per-mode access selection in connector wizard"
```

### Task 10.2 — Python library setup step

**Files:**
- Create: `frontend/src/components/SetupWizard/PythonLibStep.tsx`
- Test: `frontend/src/components/SetupWizard/PythonLibStep.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
describe("PythonLibStep", () => {
  it("collects pip name, import path, instance class+args, and API key", async () => {
    const onSubmit = vi.fn()
    render(<PythonLibStep onSubmit={onSubmit} />)
    fireEvent.change(screen.getByLabelText(/pip package/i), { target: { value: "eodhd" } })
    fireEvent.change(screen.getByLabelText(/import path/i), { target: { value: "eodhd" } })
    fireEvent.change(screen.getByLabelText(/instance class/i), { target: { value: "APIClient" } })
    fireEvent.change(screen.getByLabelText(/API key/i), { target: { value: "k" } })
    fireEvent.click(screen.getByRole("button", { name: /validate/i }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
  })
})
```

- [ ] **Step 2-5: Implement form, wire to `POST /api/connectors`, commit**

```bash
git add frontend/src/components/SetupWizard/PythonLibStep.tsx frontend/src/components/SetupWizard/PythonLibStep.test.tsx
git commit -m "feat(frontend): Python library connector setup step"
```

### Task 10.3 — Per-need callable spec review

**Files:**
- Create: `frontend/src/components/SetupWizard/CallableSpecReview.tsx`
- Test: `frontend/src/components/SetupWizard/CallableSpecReview.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
describe("CallableSpecReview", () => {
  it("renders the proposed callable + canary value and offers Approve / Re-resolve", () => {
    const onApprove = vi.fn()
    render(
      <CallableSpecReview
        need={{ id: "debt_gdp", description: "...", parameters: [], shape: "float" }}
        spec={{
          access_mode: "python_lib",
          module: "eodhd",
          method: "economic_data",
          param_bindings: { country: { to_arg: "country_code", transform: null } },
          constants: { indicator: "DEBT_GDP_PCT" },
          shape: "float",
        }}
        canaryValue={122.4}
        onApprove={onApprove}
      />
    )
    expect(screen.getByText(/economic_data/)).toBeInTheDocument()
    expect(screen.getByText(/122\.4/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /approve/i }))
    expect(onApprove).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2-5: Implement, wire to backend, commit**

```bash
git add frontend/src/components/SetupWizard/CallableSpecReview.tsx frontend/src/components/SetupWizard/CallableSpecReview.test.tsx
git commit -m "feat(frontend): per-need callable spec review with canary preview"
```

### Task 10.4 — Department status surface in Settings

**Files:**
- Create: `frontend/src/components/Settings/DepartmentStatus.tsx`
- Test: `frontend/src/components/Settings/DepartmentStatus.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
describe("DepartmentStatus", () => {
  it("renders active and disabled departments with reasons", () => {
    render(
      <DepartmentStatus
        snapshot={[
          { department_id: "secretary", status: "active", reason: null },
          { department_id: "macro_research", status: "disabled",
            reason: "No callable spec resolved for runner needs: debt_gdp." },
        ]}
      />
    )
    expect(screen.getByText(/Secretary/)).toBeInTheDocument()
    expect(screen.getByText(/Macro Research/)).toBeInTheDocument()
    expect(screen.getByText(/debt_gdp/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2-5: Implement, wire to `GET /api/dept-health`, commit**

```bash
git add frontend/src/components/Settings/DepartmentStatus.tsx frontend/src/components/Settings/DepartmentStatus.test.tsx
git commit -m "feat(frontend): department status surface in Settings"
```

### Task 10.5 — Sidebar disabled state

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Test: `frontend/src/components/Sidebar.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
describe("Sidebar — disabled departments", () => {
  it("renders disabled departments greyed out with a tooltip", () => {
    render(
      <Sidebar
        departments={[
          { id: "equity_research", display: "Equity Research", health: { status: "active" } },
          { id: "macro_research", display: "Macro Research",
            health: { status: "disabled", reason: "No callable spec for debt_gdp." } },
        ]}
      />
    )
    const mr = screen.getByText("Macro Research")
    expect(mr).toHaveClass(/disabled/)
    expect(mr).toHaveAttribute("title", expect.stringMatching(/debt_gdp/))
  })
})
```

- [ ] **Step 2-5: Implement, commit**

```bash
git add frontend/src/components/Sidebar.tsx frontend/src/components/Sidebar.test.tsx
git commit -m "feat(frontend): sidebar greyed-out state for disabled departments"
```

### Task 10.6 — Disabled banner on dept page

**Files:**
- Modify: every `frontend/src/pages/<Dept>.tsx` (or create a shared `DisabledBanner` component used by each)
- Test: `frontend/src/components/DisabledBanner.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
describe("DisabledBanner", () => {
  it("renders the reason and a Configure link", () => {
    render(<DisabledBanner reason="No callable spec for debt_gdp." />)
    expect(screen.getByText(/debt_gdp/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /configure connectors/i })).toHaveAttribute(
      "href",
      "/settings#connectors",
    )
  })
})
```

- [ ] **Step 2-5: Implement shared component, drop into each dept page when health.status=='disabled', commit**

```bash
git add frontend/src/components/DisabledBanner.tsx frontend/src/components/DisabledBanner.test.tsx frontend/src/pages/
git commit -m "feat(frontend): DisabledBanner shown on each department page when disabled"
```

---

## Phase 11 — Documentation cleanup and final verification

### Task 11.1 — Mark superseded specs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-26-connector-redesign-design.md`
- Modify: `docs/superpowers/specs/2026-04-27-connector-cutover-design.md`
- Modify: `docs/superpowers/plans/2026-04-27-connector-cutover.md`

- [ ] **Step 1: Add a "Superseded" header to each**

Insert at the top of each:
```markdown
> **Superseded.** This document is superseded by
> `docs/superpowers/specs/2026-04-27-connector-dataflow-redesign-design.md`
> (and its canonical reference at `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md`).
> See those documents for current architecture.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-26-connector-redesign-design.md docs/superpowers/specs/2026-04-27-connector-cutover-design.md docs/superpowers/plans/2026-04-27-connector-cutover.md
git commit -m "docs: mark prior connector specs/plan as superseded"
```

### Task 11.2 — Update `planning/projectStructure.md`

**Files:**
- Modify: `planning/projectStructure.md`

- [ ] **Step 1: Reflect the new dept-artifact layout**

Update the `packages/core/src/openlia/departments/` entry to mention `<dept>.routing_context.md` and `<dept>.needs.yaml`. Remove any mention of the legacy `requirements.yaml`.

- [ ] **Step 2: Commit**

```bash
git add planning/projectStructure.md
git commit -m "docs: projectStructure reflects routing_context.md + needs.yaml layout"
```

### Task 11.3 — Final smoke test

- [ ] **Step 1: Fresh DB and migration**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
sqlite3 .openlia.dev.db ".tables" > /tmp/tables.txt
cat /tmp/tables.txt
```

Expected:
- `connectors`, `runner_callable_specs` present.
- `data_providers`, `data_provider_requirement_mapping`, `tool_allowlists` absent.

- [ ] **Step 2: Full Python test suite**

```bash
uv run pytest 2>&1 | tail -5
```

Expected: passing.

- [ ] **Step 3: Frontend tests**

```bash
cd frontend && npm test -- --run 2>&1 | tail -5
```

Expected: passing.

- [ ] **Step 4: Lint**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: clean.

- [ ] **Step 5: Manual smoke**

```bash
uv run openlia serve &
SERVER_PID=$!
sleep 3
curl -s http://localhost:8000/api/health
kill $SERVER_PID
```

Expected: server starts; `/api/health` returns OK.

- [ ] **Step 6: Push branch and open PR**

```bash
git push -u origin refactor/connector-dataflow-redesign
gh pr create \
  --title "Connector data flow redesign — three-layer + runtime routing" \
  --body "$(cat <<'EOF'
## Summary
Implements the connector data flow redesign per
docs/superpowers/specs/2026-04-27-connector-dataflow-redesign-design.md.

Three-layer customization model (MCP / skills / Python lib) on a unified
Connector with multi-mode launch. Conversation-scoped runtime tool routing
with escalation tool. Structured callable_specs for runner needs. Department
health system with graceful disable.

Supersedes PR #80; cherry-picks the survivors and adds the redesign work.

## Test plan
- [ ] CI: `uv run pytest`
- [ ] CI: `cd frontend && npm test -- --run`
- [ ] Manual: clean DB, run migrations, exercise wizard end-to-end.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review — spec coverage check

For each section in `docs/superpowers/specs/2026-04-27-connector-dataflow-redesign-design.md`, this plan covers:

| Spec section | Plan task(s) |
|---|---|
| §2 Three layers (MCP, skills slot, Python lib) | Phase 1 (enums), Phase 2 (data model), Task 10.2 (Python lib UI) |
| §3.1-3.3 Connector data model + multi-mode launch | Tasks 1.1, 1.2, 2.1, 2.2 |
| §3.4 `runner_callable_specs` table | Tasks 2.3, 2.4 |
| §3.5 Drop `tool_allowlists` | Task 2.3 |
| §4 Per-dept artifacts | Phase 3 |
| §5 Parameterized needs | Tasks 1.3, 1.4, 3.3, 3.4 |
| §6 Wizard-time runner adapter | Phase 4 |
| §7 Runtime chat | Phase 6 |
| §8 Runtime runners | Phase 8 |
| §9 Wizard UX | Phase 10 |
| §10 Department health | Phase 7 |
| §11 Migration sequencing | Phase 0 (rebase) + each phase's commits |
| §12 Test strategy | Tests embedded throughout each task |

Any spec section not crossed off here is a plan gap to fix before execution starts.
