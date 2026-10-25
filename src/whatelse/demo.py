"""Demo mode: the hosted sample that judges can use without Claude Code.

Agent answers were recorded once from real runs (`tools/record_demo.py`) and are
replayed here through the normal pattern code, so everything downstream
(attribution, storage, the UI) is the same as a live run. The sample challenge is
fictional. The database is rebuilt from `demo/seed.json` on startup and on Reset.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, select

from whatelse.config import PACKAGE_DIR, Settings
from whatelse.llm import LLM, LLMError
from whatelse.models import Idea

DEMO_DIR = PACKAGE_DIR / "demo"
SEED_PATH = DEMO_DIR / "seed.json"
RECORDING_PATH = DEMO_DIR / "recording.json"

# Prefilled in the Rework panel: the note every recorded rework was made with.
REWORK_NOTE = "Make it smaller: something I could test this week with almost no money."


def call_kind(schema: dict) -> str:
    props = schema.get("properties", {})
    for key, kind in (("seeds", "round1"), ("ideas", "round2"), ("pushed", "round3"), ("title", "rework")):
        if key in props:
            return kind
    raise LLMError("failed", "demo: unknown call shape")


class ReplayLLM:
    """Answers agent calls from a recording, one recorded Generate per batch.

    The first round-1 call of each Generate picks the next batch (cycling); rounds
    2 and 3 use the same batch. Reworks are matched by the idea's title. With a
    `fallback` LLM, anything missing is fetched live and added to the recording.
    """

    def __init__(self, recording: dict, technique_labels: dict[str, str], fallback: LLM | None = None):
        self.recording = recording
        self.recording.setdefault("batches", [])
        self.recording.setdefault("reworks", {})
        self.labels = technique_labels
        self.fallback = fallback
        self._lock = Lock()
        self._round1_calls = 0
        self._batch = 0

    @classmethod
    def load(cls, technique_labels: dict[str, str], path: Path = RECORDING_PATH) -> ReplayLLM:
        return cls(json.loads(path.read_text(encoding="utf-8")), technique_labels)

    def save(self, path: Path = RECORDING_PATH) -> None:
        path.write_text(json.dumps(self.recording, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def restart(self) -> None:
        """Back to the first batch, so a fresh seed always gets the same ideas."""
        with self._lock:
            self._round1_calls = self._batch = 0

    def _technique(self, system: str) -> str:
        for key, label in self.labels.items():
            if f"**{label}**" in system:
                return key
        raise LLMError("failed", "demo: unknown technique")

    def complete(self, system: str, prompt: str, schema: dict) -> dict:
        kind = call_kind(schema)
        if kind == "rework":
            return self._rework(system, prompt, schema)
        key = self._technique(system)
        batches = self.recording["batches"]
        with self._lock:
            if kind == "round1":
                index = self._round1_calls // len(self.labels)
                self._round1_calls += 1
                if self.fallback is None:
                    if not batches:
                        raise LLMError("failed", "demo: empty recording")
                    index %= len(batches)
                self._batch = index
            index = self._batch
            if self.fallback is not None:
                while len(batches) <= index:
                    batches.append({})
            recorded = batches[index].get(kind, {}).get(key)
        if recorded is not None:
            return recorded
        if self.fallback is None:
            raise LLMError("failed", f"demo: nothing recorded for {kind} {key}")
        out = self.fallback.complete(system, prompt, schema)
        with self._lock:
            batches[index].setdefault(kind, {})[key] = out
        return out

    def _rework(self, system: str, prompt: str, schema: dict) -> dict:
        match = re.search(r"^Title: (.*)$", prompt, flags=re.M)
        title = match.group(1).strip() if match else ""
        reworks = self.recording["reworks"]
        if title in reworks:
            return reworks[title]
        if self.fallback is not None:
            out = self.fallback.complete(system, prompt, schema)
            with self._lock:
                reworks[title] = out
            return out
        if not reworks:
            raise LLMError("failed", "demo: no recorded reworks")
        # An idea nobody recorded (e.g. one the visitor typed): reuse a recorded rework.
        pool = sorted(reworks)
        return reworks[pool[sum(map(ord, title)) % len(pool)]]


def load_seed(path: Path = SEED_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_demo(engine: Engine, settings: Settings, llm: LLM, seed: dict | None = None) -> int:
    """Wipe the demo database and rebuild the sample challenge. Returns its id."""
    from whatelse.orchestrator import run_generate
    from whatelse.service import add_own_idea, create_challenge, react

    if not settings.is_demo:
        raise RuntimeError("seed_demo only runs in demo mode")
    seed = seed or load_seed()
    if isinstance(llm, ReplayLLM):
        llm.restart()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        challenge = create_challenge(session, seed["challenge"]["statement"], seed["challenge"].get("context"))
        challenge_id = challenge.id
    run_generate(engine, challenge_id, llm, settings)

    with Session(engine) as session:
        ideas = session.exec(select(Idea).where(Idea.challenge_id == challenge_id).order_by(Idea.id)).all()
        ids = [i.id for i in ideas]
        for step in seed.get("reactions", []):
            idea_id = ids[step["idea"]]
            for action, fields in step["steps"]:
                react(session, settings, idea_id, action, fields.get("tags"), fields.get("note"),
                      fields.get("verdict"))
        own = seed.get("own_idea")
        if own:
            add_own_idea(session, challenge_id, own["title"], own.get("text"))
    return challenge_id
