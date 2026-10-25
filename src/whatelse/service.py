"""All state changes. Each action writes one Event and updates the current status
in the same transaction, so the status column and the event log can't disagree."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from whatelse.models import Challenge, Event, GenerationRun, Idea, utcnow


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


@dataclass(frozen=True)
class IdeaAction:
    allowed_from: frozenset[str]
    to_status: str | None  # None = the status doesn't change
    event_type: str
    tag_kind: str | None = None  # which tag list in config applies
    note_required: str | None = None  # message shown when the note is missing
    needs_verdict: bool = False


# Every idea reaction except Rework (which also needs the agents; see orchestrator).
IDEA_ACTIONS = {
    "save": IdeaAction(frozenset({"generated"}), "saved", "saved", tag_kind="save"),
    "discard": IdeaAction(frozenset({"generated", "saved", "actioned"}), "discarded", "discarded", tag_kind="discard"),
    "action": IdeaAction(frozenset({"saved"}), "actioned", "actioned"),
    "feedback": IdeaAction(frozenset({"saved", "actioned"}), None, "feedback",
                           note_required="Write your thoughts first."),
    "progress": IdeaAction(frozenset({"actioned"}), None, "progress",
                           note_required="Write what you did or what happened."),
    "complete": IdeaAction(frozenset({"actioned"}), "completed", "completed", needs_verdict=True),
}
VERDICTS = ("worked", "partly", "didnt_work", "dropped")


def allowed_tags(settings, kind: str | None) -> set[str]:
    if kind == "save":
        return {t["key"] for t in settings.save_tags}
    if kind == "discard":
        return {t["key"] for t in settings.discard_tags}
    return set()


def react(session: Session, settings, idea_id: int, action: str, tags: list[str] | None = None,
          note: str | None = None, verdict: str | None = None) -> Idea:
    """Any idea reaction: one event plus the status change (if any), in one commit."""
    spec = IDEA_ACTIONS.get(action)
    if spec is None:
        raise ServiceError(f"Unknown action {action!r}.")
    idea = session.get(Idea, idea_id)
    if idea is None:
        raise ServiceError("That idea doesn't exist.")
    if idea.status not in spec.allowed_from:
        raise ServiceError(f"That can't be done to an idea that is {idea.status}.")
    note = (note or "").strip() or None
    if spec.note_required and not note:
        raise ServiceError(spec.note_required)
    if spec.needs_verdict and verdict not in VERDICTS:
        raise ServiceError("Choose how it went.")

    valid = allowed_tags(settings, spec.tag_kind)
    clean_tags = [t for t in dict.fromkeys(tags or []) if t in valid]
    to_status = spec.to_status or idea.status
    add_event(session, idea.challenge_id, spec.event_type, idea_id=idea.id, tags=clean_tags, note=note,
              from_status=idea.status, to_status=to_status,
              data={"verdict": verdict} if spec.needs_verdict else None)
    idea.status = to_status
    if spec.needs_verdict:
        idea.verdict = verdict
    idea.updated_at = utcnow()
    challenge = session.get(Challenge, idea.challenge_id)
    touch(challenge)
    session.add_all([idea, challenge])
    session.commit()
    session.refresh(idea)
    return idea


# Rework: a generated idea becomes `reworked` (it leaves Explore); a saved idea stays
# saved, because the person already liked it. The new idea is created by the orchestrator.
REWORK_FROM = {"generated": "reworked", "saved": "saved"}


def check_rework(idea: Idea | None, note: str | None) -> str:
    """Validate a rework request before any agent is called. Returns the cleaned note."""
    if idea is None:
        raise ServiceError("That idea doesn't exist.")
    if idea.status not in REWORK_FROM:
        raise ServiceError(f"An idea that is {idea.status} can't be reworked.")
    note = (note or "").strip()
    if not note:
        raise ServiceError("Say what you'd like changed, so the agents know how to rework it.")
    return note


def stage_rework(session: Session, idea: Idea, note: str, new_idea: Idea) -> None:
    """Stage the original's event and status change; the caller commits it with the new idea."""
    to_status = REWORK_FROM[idea.status]
    add_event(session, idea.challenge_id, "reworked", idea_id=idea.id, note=note,
              from_status=idea.status, to_status=to_status, data={"new_idea_id": new_idea.id})
    idea.status = to_status
    idea.updated_at = utcnow()
    session.add(idea)


def edit_challenge(session: Session, challenge_id: int, statement: str, context: str | None) -> Challenge:
    challenge = session.get(Challenge, challenge_id)
    if challenge is None:
        raise ServiceError("That challenge doesn't exist.")
    statement = (statement or "").strip()
    if not statement:
        raise ServiceError("The challenge can't be empty.")
    context = (context or "").strip() or None
    if statement == challenge.statement and context == challenge.context:
        return challenge
    add_event(session, challenge.id, "context_edited", data={
        "statement_changed": statement != challenge.statement,
        "context_changed": context != challenge.context,
        "previous_statement": challenge.statement,
        "previous_context": challenge.context,
    })
    challenge.statement, challenge.context, challenge.title = statement, context, title_from(statement)
    touch(challenge)
    session.add(challenge)
    session.commit()
    session.refresh(challenge)
    return challenge


OWN = "own"  # technique key for ideas the person adds themselves


def add_own_idea(session: Session, challenge_id: int, title: str, text: str | None) -> Idea:
    """The person's own idea: stored like any other, straight into the Library as saved."""
    challenge = session.get(Challenge, challenge_id)
    if challenge is None:
        raise ServiceError("That challenge doesn't exist.")
    title = " ".join((title or "").split())
    if not title:
        raise ServiceError("Give your idea a short title.")
    run = GenerationRun(challenge_id=challenge_id, kind="manual", pattern="manual", status="succeeded",
                        finished_at=utcnow())
    session.add(run)
    session.flush()
    idea = Idea(challenge_id=challenge_id, run_id=run.id, title=title[:200], text=(text or "").strip(),
                techniques=[OWN], status="saved")
    session.add(idea)
    session.flush()
    add_event(session, challenge_id, "idea_created", idea_id=idea.id, to_status="saved", data={"source": OWN})
    touch(challenge)
    session.add(challenge)
    session.commit()
    session.refresh(idea)
    return idea
