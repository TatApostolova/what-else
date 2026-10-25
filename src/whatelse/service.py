"""All state changes. Each action writes one Event and updates the current status
in the same transaction, so the status column and the event log can't disagree."""

from __future__ import annotations

from sqlmodel import Session

from whatelse.models import Challenge, Event, utcnow


class ServiceError(ValueError):
    """A refused action; the message is safe to show to the user."""


def title_from(statement: str) -> str:
    first = next((line.strip() for line in statement.splitlines() if line.strip()), "")
    return first if len(first) <= 80 else first[:79].rstrip() + "…"


def add_event(session: Session, challenge_id: int, type: str, **fields) -> Event:
    """Stage an event; the caller commits it together with the status change."""
    event = Event(challenge_id=challenge_id, type=type, **fields)
    session.add(event)
    return event


def create_challenge(session: Session, statement: str, context: str | None) -> Challenge:
    statement = (statement or "").strip()
    if not statement:
        raise ServiceError("Write a sentence or two about what you're trying to figure out.")
    challenge = Challenge(title=title_from(statement), statement=statement, context=(context or "").strip() or None)
    session.add(challenge)
    session.flush()
    add_event(session, challenge.id, "challenge_created", to_status="active")
    session.commit()
    session.refresh(challenge)
    return challenge


def touch(challenge: Challenge) -> None:
    challenge.updated_at = utcnow()
