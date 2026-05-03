"""Component B — regex-tripwire output moderation with 3-tier action model.

Patterns are deliberately conservative; we tune from real audit data after
launch. Categories whose action is REPLACE preempt WARN/LOG; if any
REPLACE tripwire fires we emit a single REPLACE decision."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ActionTier(StrEnum):
    REPLACE = "replaced"
    WARN = "warned"
    LOG = "logged"


@dataclass(frozen=True)
class Tripwire:
    category: str
    pattern: re.Pattern[str]
    action: ActionTier
    message: str = ""


@dataclass(frozen=True)
class ModerationMatch:
    category: str
    action: ActionTier
    pattern: str
    matched_text: str
    message: str


@dataclass(frozen=True)
class ActionDecision:
    action: ActionTier
    category: str
    message: str
    matches: list[ModerationMatch]


_REPLACE_LEAKED = "I don't share my underlying instructions. What can I help you look up?"
_REPLACE_BROKEN = (
    "I'm Lia — Little Investor Assistant — not that. What can I help you with on the desk?"
)


_TRIPWIRES: tuple[Tripwire, ...] = (
    Tripwire(
        category="leaked_prompt",
        pattern=re.compile(
            r"#\s*(?:Who you are|How you sound \(the seven voice rules\)|What you won't do)",
        ),
        action=ActionTier.REPLACE,
        message=_REPLACE_LEAKED,
    ),
    Tripwire(
        category="broken_character",
        pattern=re.compile(
            r"\b(?:I am|I'm)\s+(?:ChatGPT|GPT-?4|GPT-?5|Claude|DAN|an AI language model)\b",
            re.IGNORECASE,
        ),
        action=ActionTier.REPLACE,
        message=_REPLACE_BROKEN,
    ),
    Tripwire(
        category="advice_phrasing",
        pattern=re.compile(
            r"\b(?:I recommend|you should|my recommendation is)"
            r"\s+(?:you\s+)?(?:buy|sell|short|sell short)\b"
            r"|\b(?:buy|sell)\s+(?:this|the)\s+(?:stock|ticker)\b",
            re.IGNORECASE,
        ),
        action=ActionTier.WARN,
        message=(
            "Flagged: directive advice phrasing — Lia normally lays out the case, not the call."
        ),
    ),
    Tripwire(
        category="fabricated_quote",
        pattern=re.compile(
            r"\b(?:Goldman(?: Sachs)?|Morgan Stanley|JPMorgan|JP Morgan|Bank of America|"
            r"Citigroup|Wells Fargo|UBS|Barclays|Deutsche Bank)\b[^.]{0,80}"
            r"\b(?:said|wrote|noted|believes|thinks|sees)\b",
        ),
        action=ActionTier.WARN,
        message="Flagged: possible unverified attribution — verify against a primary source.",
    ),
    Tripwire(
        category="disclaimer_regression",
        pattern=re.compile(
            r"\b(?:this is not (?:financial )?advice"
            r"|consult a (?:licensed )?(?:financial )?advisor"
            r"|I am an AI language model"
            r"|as an AI language model)\b",
            re.IGNORECASE,
        ),
        action=ActionTier.LOG,
    ),
    Tripwire(
        category="price_prediction",
        pattern=re.compile(
            r"\$?[A-Z]{1,5}\b[^.]{0,80}\b(?:will|is going to)\s+"
            r"(?:hit|reach|fall to|drop to)\s+\$?\d",
        ),
        action=ActionTier.WARN,
        message="Flagged: certain-prediction phrasing — markets don't work that way.",
    ),
    Tripwire(
        category="padding",
        pattern=re.compile(
            r"\b(?:great question|happy to help|I hope this helps"
            r"|let me know if (?:you have )?(?:any )?(?:more )?questions)\b",
            re.IGNORECASE,
        ),
        action=ActionTier.LOG,
    ),
)


def scan(text: str) -> list[ModerationMatch]:
    matches: list[ModerationMatch] = []
    for tw in _TRIPWIRES:
        m = tw.pattern.search(text)
        if m is None:
            continue
        matches.append(
            ModerationMatch(
                category=tw.category,
                action=tw.action,
                pattern=tw.pattern.pattern,
                matched_text=m.group(0)[:200],
                message=tw.message,
            )
        )
    return matches


def decide_action(matches: list[ModerationMatch]) -> ActionDecision | None:
    if not matches:
        return None
    for tier in (ActionTier.REPLACE, ActionTier.WARN, ActionTier.LOG):
        for m in matches:
            if m.action is tier:
                return ActionDecision(
                    action=tier,
                    category=m.category,
                    message=m.message,
                    matches=matches,
                )
    return None
