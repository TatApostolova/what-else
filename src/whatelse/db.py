"""Database engine for the current mode (real or demo)."""

from __future__ import annotations

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from whatelse import models  # noqa: F401 - registers the tables
from whatelse.config import Settings
from whatelse.models import GenerationRun, utcnow


def make_engine(settings: Settings) -> Engine:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{settings.db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    SQLModel.metadata.create_all(engine)
    fail_stuck_runs(engine)
    return engine


def fail_stuck_runs(engine: Engine) -> int:
    """A run left `running` by a crash would block Generate forever."""
    with Session(engine) as session:
        stuck = session.exec(select(GenerationRun).where(GenerationRun.status == "running")).all()
        for run in stuck:
            run.status = "failed"
            run.error = "interrupted (app restarted)"
            run.finished_at = utcnow()
            session.add(run)
        session.commit()
        return len(stuck)
