"""Learning boundary: the only place that decides what history the agents see.

POC rule: everything for this challenge, newest first, capped at about 40 items.
Ideas still waiting for a reaction are listed by title only, to avoid repeats —
never as a preference. Nothing from other challenges is ever read.
A smarter analysis layer can replace `build_context` without touching the agents.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from whatelse.models import Challenge, Event, Idea

HISTORY_CAP = 40
TEXT_LIMIT = 220
VERDICTS = {"worked": "Worked", "partly": "Partly worked", "didnt_work": "Didn't work", "dropped": "Dropped"}


@dataclass(frozen=True)
class AgentContext:
    statement: str
    context: str | None = None
    history: str = ""


def _short(text: str, limit: int = TEXT_LIMIT) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _reasons(event: Event | None, tag_labels: dict[str, str]) -> str:
    if event is None:
        return ""
    parts = []
    if event.tags:
        parts.append("reasons: " + ", ".join(tag_labels.get(t, t.replace("_", " ")) for t in event.tags))
    if event.note:
        parts.append(f'note: "{_short(event.note, 300)}"')
    return " — " + "; ".join(parts) if parts else ""


def build_context(session: Session, challenge_id: int, tag_labels: dict[str, str] | None = None) -> AgentContext:
    challenge = session.get(Challenge, challenge_id)
    if challenge is None:
        raise LookupError(f"challenge {challenge_id} not found")
    tag_labels = tag_labels or {}

    ideas = {i.id: i for i in session.exec(select(Idea).where(Idea.challenge_id == challenge_id))}
    events: dict[int, list[Event]] = {}
    for e in session.exec(
        select(Event).where(Event.challenge_id == challenge_id, Event.idea_id.is_not(None)).order_by(Event.id)
    ):
        events.setdefault(e.idea_id, []).append(e)

    def last(idea_id: int, type_: str) -> Event | None:
        return next((e for e in reversed(events.get(idea_id, [])) if e.type == type_), None)

    def last_activity(idea: Idea) -> int:
        return max((e.id for e in events.get(idea.id, [])), default=0)

    liked, rejected, reworked, tried, pending = [], [], [], [], []
    for idea in sorted(ideas.values(), key=last_activity, reverse=True):
        feedback = [e for e in events.get(idea.id, []) if e.type == "feedback" and (e.note or e.tags)]
        later = "".join(f'\n  later feedback: "{_short(e.note or "", 200)}"' for e in feedback if e.note)

        if idea.status == "generated":
            pending.append(f'- "{idea.title}"')
        elif idea.status == "discarded":
            rejected.append(f'- "{idea.title}": {_short(idea.text)}{_reasons(last(idea.id, "discarded"), tag_labels)}')
        elif idea.status == "saved":
            own = " (the person's own idea)" if "own" in idea.techniques else ""
            text = f": {_short(idea.text)}" if idea.text else ""
            liked.append(f'- "{idea.title}"{own}{text}{_reasons(last(idea.id, "saved"), tag_labels)}{later}')
        elif idea.status in ("actioned", "completed"):
            progress = [e for e in events.get(idea.id, []) if e.type == "progress" and e.note]
            lines = [f'- "{idea.title}": {_short(idea.text)}']
            lines += [f'  progress: "{_short(e.note, 200)}"' for e in progress[-3:]]
            if idea.status == "completed":
                done = last(idea.id, "completed")
                verdict = VERDICTS.get(idea.verdict or "", idea.verdict or "finished")
                lines.append(f"  outcome: {verdict}" + (f' — "{_short(done.note, 200)}"' if done and done.note else ""))
            else:
                lines.append("  outcome: still in progress")
            tried.append("\n".join(lines) + later)

        # Reworks are recorded on the original, whatever its status is now.
        for e in events.get(idea.id, []):
            if e.type == "reworked":
                new = ideas.get((e.data or {}).get("new_idea_id"))
                result = f' → became "{new.title}"' if new else ""
                reworked.append(f'- "{idea.title}" — asked to change: "{_short(e.note or "", 300)}"{result}')

    sections = [
        ("Tried (experiments and their outcomes — the strongest signal)", tried),
        ("Liked (saved ideas, with the person's reasons)", liked),
        ("Rejected (discarded ideas, with reasons)", rejected),
        ("Reworked (what the person asked to change)", reworked),
        ("Already suggested, no reaction yet (titles only — don't repeat these)", pending),
    ]
    budget = HISTORY_CAP
    parts = []
    for heading, items in sections:
        if not items or budget <= 0:
            continue
        kept = items[:budget]
        budget -= len(kept)
        parts.append(f"### {heading}\n" + "\n".join(kept))

    return AgentContext(statement=challenge.statement, context=challenge.context, history="\n\n".join(parts))
