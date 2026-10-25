"""Record the agent answers that demo mode replays. Uses your Claude Code login.

    .venv\\Scripts\\python.exe tools\\record_demo.py [--batches 3]

Anything already in src/whatelse/demo/recording.json is replayed, not re-asked,
so the script can be rerun after editing seed.json or to add batches. Work goes
into a throwaway database; the recording is saved after every step.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import tempfile
from pathlib import Path

from sqlmodel import Session, select

from whatelse.config import load_settings
from whatelse.db import make_engine
from whatelse.demo import RECORDING_PATH, REWORK_NOTE, ReplayLLM, seed_demo
from whatelse.llm import ClaudeCLI
from whatelse.models import Idea
from whatelse.orchestrator import load_techniques, run_generate, run_rework


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batches", type=int, default=3, help="recorded Generates, the seeded one included")
    parser.add_argument("--no-reworks", action="store_true", help="only record the Generates")
    args = parser.parse_args()

    data_dir = Path(tempfile.mkdtemp(prefix="whatelse-record-"))
    settings = dataclasses.replace(load_settings("demo"), data_dir=data_dir)
    engine = make_engine(settings)
    labels = {t.key: t.label for t in load_techniques(settings.techniques)}
    recording = json.loads(RECORDING_PATH.read_text(encoding="utf-8")) if RECORDING_PATH.exists() else {}
    live = ClaudeCLI(model=settings.model, timeout=settings.timeout_seconds, effort=settings.effort,
                     log_path=data_dir / "agent-calls.jsonl")
    llm = ReplayLLM(recording, labels, fallback=live)

    print("Batch 1 (the seeded sample)...")
    challenge_id = seed_demo(engine, settings, llm)
    llm.save()
    for n in range(2, args.batches + 1):
        print(f"Batch {n}...")
        run_generate(engine, challenge_id, llm, settings)
        llm.save()

    if args.no_reworks:
        return
    with Session(engine) as session:
        ideas = session.exec(select(Idea).where(Idea.status.in_(("generated", "saved"))).order_by(Idea.id)).all()
        todo = [(i.id, i.title) for i in ideas if i.title not in recording["reworks"]]
    for count, (idea_id, title) in enumerate(todo, start=1):
        print(f"Rework {count}/{len(todo)}: {title}")
        run_rework(engine, idea_id, REWORK_NOTE, llm, settings)
        llm.save()
    print(f"Saved {RECORDING_PATH}")


if __name__ == "__main__":
    main()
