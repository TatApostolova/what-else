"""Learning boundary: the only place that decides what history the agents see."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from whatelse.models import Challenge


@dataclass(frozen=True)
class AgentContext:
    statement: str
    context: str | None = None
    history: str = ""


def build_context(session: Session, challenge_id: int) -> AgentContext:
    challenge = session.get(Challenge, challenge_id)
    if challenge is None:
        raise LookupError(f"challenge {challenge_id} not found")
    return AgentContext(statement=challenge.statement, context=challenge.context)
