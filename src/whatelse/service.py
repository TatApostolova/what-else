"""All state changes. Each action writes one Event and updates the current status
in the same transaction, so the status column and the event log can't disagree."""

from __future__ import annotations

from sqlmodel import Session

from whatelse.models import Challenge, Event, Idea, utcnow


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


# Idea reactions: action -> (statuses it's allowed from, new status, event type, tag list in config).
IDEA_ACTIONS = {
    "save": ({"generated"}, "saved", "saved", "save"),
    "discard": ({"generated", "saved", "actioned"}, "discarded", "discarded", "discard"),
}


def allowed_tags(settings, kind: str | None) -> set[str]:
    if kind == "save":
        return {t["key"] for t in settings.save_tags}
    if kind == "discard":
        return {t["key"] for t in settings.discard_tags}
    return set()


def react(session: Session, settings, idea_id: int, action: str,
          tags: list[str] | None = None, note: str | None = None) -> Idea:
    """Save or discard an idea: one event plus the status change, in one commit."""
    if action not in IDEA_ACTIONS:
        raise ServiceError(f"Unknown action {action!r}.")
    allowed_from, to_status, event_type, tag_kind = IDEA_ACTIONS[action]
    idea = session.get(Idea, idea_id)
    if idea is None:
        raise ServiceError("That idea doesn't exist.")
    if idea.status not in allowed_from:
        raise ServiceError(f"An idea that is {idea.status} can't be {to_status}.")

    valid = allowed_tags(settings, tag_kind)
    clean_tags = [t for t in dict.fromkeys(tags or []) if t in valid]
    add_event(session, idea.challenge_id, event_type, idea_id=idea.id, tags=clean_tags,
              note=(note or "").strip() or None, from_status=idea.status, to_status=to_status)
    idea.status = to_status
    idea.updated_at = utcnow()
    challenge = session.get(Challenge, idea.challenge_id)
    touch(challenge)
    session.add_all([idea, challenge])
    session.commit()
    session.refresh(idea)
    return idea
