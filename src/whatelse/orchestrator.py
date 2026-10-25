"""Loads techniques and runs a collaboration pattern."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from sqlmodel import Session, select

from whatelse.config import PACKAGE_DIR, Settings
from whatelse.context import AgentContext, build_context
from whatelse.llm import LLM, LLMError
from whatelse.models import GenerationRun, Idea, utcnow
from whatelse.patterns import PatternResult
from pydantic import BaseModel, Field

from whatelse.patterns import challenge_block, render, system_prompt
from whatelse.models import Challenge
from whatelse.service import add_event, check_rework, require_active, stage_rework, touch

TECHNIQUES_DIR = PACKAGE_DIR / "techniques"
PATTERNS = ("collaborative",)


@dataclass(frozen=True)
class Technique:
    key: str
    label: str
    body: str


def _parse_technique(text: str) -> Technique:
    """Minimal frontmatter: `---`, `key: value` lines, `---`, then the body."""
    _, front, body = text.split("---", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines())
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    return Technique(key=meta["key"], label=meta["label"], body=body.strip())


def load_techniques(keys: list[str]) -> list[Technique]:
    return [_parse_technique((TECHNIQUES_DIR / f"{k}.md").read_text(encoding="utf-8")) for k in keys]


def technique_label(keys: list[str], techniques: list[Technique]) -> str:
    """Card label: own technique first, then what it built on, e.g. 'SCAMPER ← ANALOGIES + REVERSE THINKING'."""
    labels = {t.key: t.label.upper() for t in techniques} | {"own": "YOUR IDEA"}
    names = [labels.get(k, k.replace("_", " ").upper()) for k in keys]
    if len(names) == 1:
        return names[0]
    return f"{names[0]} ← {' + '.join(names[1:])}"


def generate(ctx: AgentContext, llm: LLM, settings: Settings, pattern: str | None = None) -> PatternResult:
    """Run a pattern. Raises LLMError on any failure; never returns partial results."""
    name = pattern or settings.pattern
    if name not in PATTERNS:
        raise ValueError(f"Unknown pattern {name!r}")
    module = importlib.import_module(f"whatelse.patterns.{name}")
    result = module.run(ctx, llm, load_techniques(settings.techniques), settings)
    if not result.ideas:
        raise LLMError("failed", "pattern returned no ideas")
    return result


class GenerateRefused(Exception):
    """Generate can't start (e.g. a run is already in progress)."""


def run_generate(engine, challenge_id: int, llm: LLM, settings: Settings, requested: str = "default") -> list[Idea]:
    """Create a run, call the agents, and store the ideas — or mark the run failed.

    The database session is closed while the agents work, so a slow Generate
    never holds the database. Raises LLMError (run marked failed, no ideas
    stored) or GenerateRefused.
    """
    pattern = settings.pattern if requested == "default" else requested
    with Session(engine) as session:
        busy = session.exec(
            select(GenerationRun).where(
                GenerationRun.challenge_id == challenge_id, GenerationRun.status == "running"
            )
        ).first()
        if busy:
            raise GenerateRefused("The agents are already working on this challenge.")
        require_active(session.get(Challenge, challenge_id))
        ctx = build_context(session, challenge_id, settings.tag_labels)
        run = GenerationRun(
            challenge_id=challenge_id, kind="generate", pattern=pattern, model=settings.model,
            data={"requested": requested, "effort": settings.effort},
        )
        session.add(run)
        session.commit()
        run_id = run.id

    try:
        result = generate(ctx, llm, settings, pattern)
    except Exception as exc:
        error = exc if isinstance(exc, LLMError) else LLMError("failed", repr(exc))
        with Session(engine) as session:
            run = session.get(GenerationRun, run_id)
            run.status, run.error, run.finished_at = "failed", str(error)[:500], utcnow()
            session.add(run)
            session.commit()
        raise error from exc

    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        ideas = [
            Idea(challenge_id=challenge_id, run_id=run_id, title=d.title, text=d.text,
                 techniques=d.techniques, built_on=d.built_on, how=d.how)
            for d in result.ideas
        ]
        session.add_all(ideas)
        session.flush()
        for idea in ideas:
            add_event(session, challenge_id, "idea_created", idea_id=idea.id, to_status="generated")
        run.status, run.finished_at = "succeeded", utcnow()
        run.data = {**run.data, **result.data}
        challenge = session.get(Challenge, challenge_id)
        touch(challenge)
        session.add_all([run, challenge])
        session.commit()
        for idea in ideas:
            session.refresh(idea)
        return ideas


class _ReworkOut(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    how: str = ""


REWORK_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "text": {"type": "string"}, "how": {"type": "string"}},
    "required": ["title", "text", "how"],
    "additionalProperties": False,
}


def run_rework(engine, idea_id: int, note: str, llm: LLM, settings: Settings) -> Idea:
    """One call with the original idea's own technique, the note and the history.

    On success the new idea and the original's status change are stored together;
    on failure the original is left exactly as it was. Raises ServiceError or LLMError.
    """
    techniques = {t.key: t for t in load_techniques(settings.techniques)}
    with Session(engine) as session:
        original = session.get(Idea, idea_id)
        note = check_rework(original, note)
        require_active(session.get(Challenge, original.challenge_id))
        busy = session.exec(select(GenerationRun).where(
            GenerationRun.challenge_id == original.challenge_id, GenerationRun.status == "running")).first()
        if busy:
            raise GenerateRefused("The agents are already working on this challenge.")
        ctx = build_context(session, original.challenge_id, settings.tag_labels)
        lead = techniques.get(original.techniques[0]) or next(iter(techniques.values()))
        prompt = render(
            "rework", challenge=challenge_block(ctx), title=original.title, text=original.text,
            techniques=", ".join(techniques[k].label for k in original.techniques if k in techniques) or lead.label,
            note=note, label=lead.label,
        )
        run = GenerationRun(challenge_id=original.challenge_id, kind="rework", pattern="rework",
                            model=settings.model, data={"idea_id": idea_id, "effort": settings.effort})
        session.add(run)
        session.commit()
        run_id, challenge_id = run.id, original.challenge_id
        original_techniques = list(original.techniques)
        if original_techniques[0] not in techniques:  # e.g. the person's own idea
            original_techniques = [lead.key] + original_techniques

    try:
        out = _ReworkOut.model_validate(llm.complete(system_prompt(lead), prompt, REWORK_SCHEMA))
    except Exception as exc:
        error = exc if isinstance(exc, LLMError) else LLMError("failed", repr(exc))
        with Session(engine) as session:
            run = session.get(GenerationRun, run_id)
            run.status, run.error, run.finished_at = "failed", str(error)[:500], utcnow()
            session.add(run)
            session.commit()
        raise error

    with Session(engine) as session:
        original = session.get(Idea, idea_id)
        new = Idea(challenge_id=challenge_id, run_id=run_id, parent_idea_id=idea_id,
                   title=out.title.strip(), text=out.text.strip(), techniques=original_techniques,
                   how=out.how.strip() or None)
        session.add(new)
        session.flush()
        add_event(session, challenge_id, "idea_created", idea_id=new.id, to_status="generated",
                  data={"parent_idea_id": idea_id})
        stage_rework(session, original, note, new)
        run = session.get(GenerationRun, run_id)
        run.status, run.finished_at = "succeeded", utcnow()
        run.data = {**run.data, "new_idea_id": new.id}
        challenge = session.get(Challenge, challenge_id)
        touch(challenge)
        session.add_all([run, challenge])
        session.commit()
        session.refresh(new)
        return new
