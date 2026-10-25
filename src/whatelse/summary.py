"""Closing summary, built from stored rows with ordinary queries (no AI call)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session, select

from whatelse.models import Challenge, Event, Idea


@dataclass
class Summary:
    challenge: Challenge
    counts: dict[str, int]
    experiments: list[Idea] = field(default_factory=list)
    saved: list[Idea] = field(default_factory=list)


def build_summary(session: Session, challenge_id: int) -> Summary:
    challenge = session.get(Challenge, challenge_id)
    ideas = list(session.exec(select(Idea).where(Idea.challenge_id == challenge_id).order_by(Idea.id)))
    events = list(session.exec(select(Event).where(Event.challenge_id == challenge_id, Event.idea_id.is_not(None))))

    def ever(type_: str) -> int:
        """How many distinct ideas this ever happened to (reopened history included)."""
        return len({e.idea_id for e in events if e.type == type_})

    own = [i for i in ideas if "own" in i.techniques]
    counts = {
        "generated": len(ideas) - len(own),
        "own": len(own),
        "saved": ever("saved") + len(own),
        "discarded": ever("discarded"),
        "reworked": ever("reworked"),
        "actioned": ever("actioned"),
        "completed": ever("completed"),
    }
    experiments = sorted(
        (i for i in ideas if i.status in ("actioned", "completed")),
        key=lambda i: (i.status == "actioned", i.id),
    )
    saved = [i for i in ideas if i.status == "saved"]
    return Summary(challenge=challenge, counts=counts, experiments=experiments, saved=saved)
