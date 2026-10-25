import dataclasses

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape
from sqlmodel import Session, select

from whatelse.config import load_settings
from whatelse.db import make_engine
from whatelse.demo import REWORK_NOTE, ReplayLLM, load_seed, seed_demo
from whatelse.llm import FakeLLM
from whatelse.models import Challenge, Idea
from whatelse.orchestrator import load_techniques
from whatelse.web import create_app


@pytest.fixture
def demo_settings(tmp_path):
    return dataclasses.replace(load_settings("demo"), data_dir=tmp_path)


@pytest.fixture
def client(demo_settings):
    return TestClient(create_app(demo_settings))


def ideas(settings, status=None):
    with Session(make_engine(settings)) as s:
        query = select(Idea).order_by(Idea.id)
        if status:
            query = query.where(Idea.status == status)
        return s.exec(query).all()


def test_starts_with_the_sample_challenge(client, demo_settings):
    page = client.get("/").text
    assert "Sample mode" in page and "Reset demo" in page
    assert "bookshop" in page
    seed = load_seed()
    statuses = [i.status for i in ideas(demo_settings)]
    assert statuses.count("saved") == 2  # one saved idea plus the person's own
    assert statuses.count("actioned") == 1 and statuses.count("completed") == 1
    assert statuses.count("discarded") == 2
    assert statuses.count("generated") == 10 - len(seed["reactions"])


def test_generate_replays_the_next_recorded_batch(client, demo_settings):
    before = {i.title for i in ideas(demo_settings)}
    html = client.post("/challenges/1/generate").text
    new = [i for i in ideas(demo_settings, "generated") if i.title not in before]
    assert len(new) == 10
    assert escape(new[0].title) in html and "couldn" not in html


def test_rework_replays_with_the_suggested_note(client, demo_settings):
    idea = ideas(demo_settings, "generated")[0]
    panel = client.get(f"/ideas/{idea.id}/panel/rework").text
    assert REWORK_NOTE in panel
    client.post(f"/ideas/{idea.id}/rework", data={"note": "anything at all"})
    reworked = [i for i in ideas(demo_settings) if i.parent_idea_id == idea.id]
    assert len(reworked) == 1 and reworked[0].title != idea.title


def test_reset_restores_the_sample(client, demo_settings):
    client.post("/challenges/1/generate")
    client.post("/challenges/1/delete", data={"confirm": "yes"})
    resp = client.post("/demo/reset", follow_redirects=False)
    assert resp.status_code == 303
    with Session(make_engine(demo_settings)) as s:
        assert len(s.exec(select(Challenge)).all()) == 1
    assert len(ideas(demo_settings)) == 11  # ten generated plus the person's own


def test_no_new_challenges_or_shutdown_in_demo(client):
    assert "aren't live" in client.get("/challenges/new").text
    resp = client.post("/challenges", data={"statement": "Mine"}, follow_redirects=False)
    assert resp.status_code == 303
    assert "Mine" not in client.get("/").text
    token = client.get("/_version").text
    assert client.post("/_shutdown", data={"token": token}).status_code == 403


def test_reset_is_missing_outside_demo(settings):
    client = TestClient(create_app(settings, FakeLLM()))
    assert client.post("/demo/reset").status_code == 404
    assert "Sample mode" not in client.get("/").text


def test_replay_records_missing_answers_through_the_fallback(demo_settings):
    labels = {t.key: t.label for t in load_techniques(demo_settings.techniques)}
    fake = FakeLLM()
    llm = ReplayLLM({}, labels, fallback=fake)
    engine = make_engine(demo_settings)
    seed_demo(engine, demo_settings, llm, {"challenge": {"statement": "A test"}})
    assert len(fake.calls) == 15  # three rounds of five agents
    replay = ReplayLLM(llm.recording, labels)
    seed_demo(engine, demo_settings, replay, {"challenge": {"statement": "A test"}})
    assert len(ideas(demo_settings)) == 10 and len(fake.calls) == 15  # replayed, nothing asked again
