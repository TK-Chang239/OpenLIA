"""Setup Wizard service — status resolution, step state, session token."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from openlia_server.db.models.auth import SignupPolicy, User
from openlia_server.db.models.infrastructure import ConfigStore, WizardState

Mode = Literal["personal", "company"]

ENV_KEYS: dict[str, str] = {
    "mode": "OPENLIA_MODE",
    "bind_host": "OPENLIA_BIND_HOST",
    "bind_port": "OPENLIA_BIND_PORT",
    "db_url": "OPENLIA_DB_URL",
    "auth_enabled": "OPENLIA_AUTH_ENABLED",
    "cookie_secure": "OPENLIA_COOKIE_SECURE",
    "trust_proxy_headers": "OPENLIA_TRUST_PROXY_HEADERS",
    "signup_policy": "OPENLIA_SIGNUP_POLICY",
    "signup_allowed_domains": "OPENLIA_SIGNUP_ALLOWED_DOMAINS",
}

STEP_ORDER_PERSONAL = ["mode", "identity", "models", "providers", "review"]
STEP_ORDER_COMPANY = ["mode", "admin", "models", "providers", "access_control", "review"]


@dataclass(slots=True)
class WizardStatus:
    mode: Mode
    wizard_completed: bool
    current_step: str
    completed_steps: list[str]
    env_overrides: dict[str, str] = field(default_factory=dict)


class AdminExistsError(Exception):
    pass


def _load_config(db: Session, key: str) -> object | None:
    row = db.get(ConfigStore, key)
    return row.value if row is not None else None


def _env_overrides(env: dict[str, str]) -> dict[str, str]:
    return {slot: env_key for slot, env_key in ENV_KEYS.items() if env.get(env_key)}


def _resolve_mode(db: Session, env: dict[str, str]) -> Mode:
    if env.get("OPENLIA_MODE") in ("personal", "company"):
        return env["OPENLIA_MODE"]  # type: ignore[return-value]
    db_mode = _load_config(db, "wizard.mode")
    if db_mode in ("personal", "company"):
        return db_mode  # type: ignore[return-value]
    return "personal"


def _is_completed(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return (value or "").lower() == "true"  # type: ignore[union-attr]


def _load_or_create_state(db: Session) -> WizardState:
    state = db.get(WizardState, 1)
    if state is None:
        state = WizardState(id=1, current_step="mode", completed_steps=[], step_data={})
        db.add(state)
        db.flush()
    return state


def get_status(db: Session, env: dict[str, str]) -> WizardStatus:
    completed = _is_completed(_load_config(db, "wizard.completed"))
    mode = _resolve_mode(db, env)
    state = _load_or_create_state(db)
    return WizardStatus(
        mode=mode,
        wizard_completed=completed,
        current_step=state.current_step,
        completed_steps=list(state.completed_steps or []),
        env_overrides=_env_overrides(env),
    )


def rotate_session_token(db: Session) -> str:
    state = _load_or_create_state(db)
    token = secrets.token_urlsafe(32)
    state.active_session_token = token
    db.flush()
    return token


def verify_session_token(db: Session, token: str | None) -> bool:
    if not token:
        return False
    state = db.get(WizardState, 1)
    return state is not None and state.active_session_token == token


def set_mode(db: Session, mode: Mode) -> None:
    # Cross-plan contract: WizardState.mode is the source of truth during
    # setup; config_store.wizard.mode is the durable record after finalize.
    # We write both so reads from either source match while the wizard runs.
    row = db.get(ConfigStore, "wizard.mode")
    if row is None:
        db.add(ConfigStore(key="wizard.mode", value=mode))
    else:
        row.value = mode
    state = _load_or_create_state(db)
    state.mode = mode
    db.flush()


def advance_step(db: Session, completed: str, mode: Mode) -> None:
    state = _load_or_create_state(db)
    order = STEP_ORDER_COMPANY if mode == "company" else STEP_ORDER_PERSONAL
    if completed not in order:
        return
    done = list(state.completed_steps or [])
    if completed not in done:
        done.append(completed)
    idx = order.index(completed)
    state.current_step = order[idx + 1] if idx + 1 < len(order) else order[-1]
    state.completed_steps = done
    db.flush()


def upsert_local_user(db: Session, display_name: str) -> User:
    user = db.query(User).filter_by(email="local@openlia.local").one_or_none()
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            email="local@openlia.local",
            password_hash=None,
            display_name=display_name,
            is_admin=False,
            is_disabled=False,
        )
        db.add(user)
    else:
        user.display_name = display_name
    db.flush()
    return user


def create_first_admin(db: Session, email: str, password: str, display_name: str) -> User:
    from openlia_server.services.auth.passwords import hash_password

    if db.query(User).filter_by(is_admin=True).first() is not None:
        raise AdminExistsError()
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        is_admin=True,
        is_disabled=False,
    )
    db.add(user)
    db.flush()
    return user


def set_signup_policy(db: Session, *, policy: str, allowed_domains: str | None) -> None:
    row = db.get(SignupPolicy, 1)
    domains: list[str] = [d.strip() for d in (allowed_domains or "").split(",") if d.strip()]
    if row is None:
        row = SignupPolicy(id=1, mode=policy, allowed_email_domains=domains)
        db.add(row)
    else:
        row.mode = policy
        row.allowed_email_domains = domains
    db.flush()


def set_config(db: Session, key: str, value: str) -> None:
    row = db.get(ConfigStore, key)
    if row is None:
        db.add(ConfigStore(key=key, value=value))
    else:
        row.value = value
    db.flush()


def finalize(db: Session, mode: Mode) -> None:
    set_config(db, "wizard.completed", "true")
    set_config(db, "wizard.mode", mode)
    # Mode-default signup policy seeded on wizard completion per
    # `database-design.md` §3 `signup_policy` ("Seeded on wizard completion:
    # personal mode -> `closed`; company mode -> `invite_only`"). The seed is
    # idempotent: if the admin already set a policy via `set_signup_policy`
    # during the wizard, this call is a no-op.
    from openlia_server.services.auth import signup_policy as _signup_policy

    _signup_policy.seed_signup_policy(db, mode_flag=mode)
    state = _load_or_create_state(db)
    state.active_session_token = None
    state.completed_steps = []
    state.current_step = "done"
    state.step_data = {}
    db.flush()
