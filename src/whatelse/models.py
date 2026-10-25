"""Database tables. All timestamps are timezone-aware UTC; tags and lists are JSON."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """SQLite drops time zones; store UTC and hand it back as aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("naive datetime; use utcnow()")
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


def _created() -> Any:
    return Field(default_factory=utcnow, sa_type=UTCDateTime)


class Challenge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    statement: str
    context: str | None = None
    status: str = "active"  # active | paused | achieved | abandoned
    outcome_note: str | None = None
    created_at: datetime = _created()
    updated_at: datetime = _created()


class GenerationRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    kind: str  # generate | rework
    pattern: str
    model: str | None = None
    status: str = "running"  # running | succeeded | failed
    error: str | None = None
    data: dict = Field(default_factory=dict, sa_type=JSON)
    started_at: datetime = _created()
    finished_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class Idea(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    run_id: int = Field(foreign_key="generationrun.id", index=True)
    parent_idea_id: int | None = Field(default=None, foreign_key="idea.id")
    title: str
    text: str
    techniques: list = Field(default_factory=list, sa_type=JSON)  # own technique first
    built_on: list = Field(default_factory=list, sa_type=JSON)
    how: str | None = None
    status: str = "generated"  # generated | saved | reworked | actioned | completed | discarded
    verdict: str | None = None  # worked | partly | didnt_work | dropped
    created_at: datetime = _created()
    updated_at: datetime = _created()


class Event(SQLModel, table=True):
    """Append-only history. Rows are never edited or deleted."""

    id: int | None = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    idea_id: int | None = Field(default=None, foreign_key="idea.id", index=True)
    type: str
    tags: list = Field(default_factory=list, sa_type=JSON)
    note: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    data: dict | None = Field(default=None, sa_type=JSON)
    created_at: datetime = _created()
