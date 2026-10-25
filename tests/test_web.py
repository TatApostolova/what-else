import threading
from html import unescape

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from whatelse.db import make_engine
from whatelse.llm import FakeLLM, LLMError
from whatelse.models import Event, GenerationRun, Idea
from whatelse.web import create_app


@pytest.fixture
def make_client(settings):
    def make(llm=None):
        return TestClient(create_app(settings, llm or FakeLLM()))
    return make


def start(client, statement="How do I get noticed by teams doing interesting work?", context=""):
    return client.post("/challenges", data={"statement": statement, "context": context}, follow_redirects=False)


def test_welcome_then_dashboard(make_client):
    client = make_client()
    assert "Start a Challenge" in client.get("/").text
    start(client)
    page = client.get("/").text
    assert "Your challenges" in page and "How do I get noticed" in page


def test_create_challenge_opens_explore(make_client, settings):
    client = make_client()
    resp = start(client, context="Some background")
    assert resp.status_code == 303 and resp.headers["location"] == "/challenges/1"
    page = client.get("/challenges/1").text
    assert "Some background" in page and "Generate" in page
    with Session(make_engine(settings)) as s:
        assert [e.type for e in s.exec(select(Event)).all()] == ["challenge_created"]


def test_empty_statement_blocked(make_client):
    client = make_client()
    resp = start(client, statement="   ", context="kept")
    assert resp.status_code == 400
    assert "Write a sentence or two" in resp.text and "kept" in resp.text
    assert "Start a Challenge" in client.get("/").text  # nothing created


def test_generate_stores_ideas_with_events(make_client, settings):
    client = make_client()
    start(client)
    html = client.post("/challenges/1/generate").text
    assert html.count('class="card idea"') == 10
    assert "Explore <span class=\"count\">10</span>" in html
    with Session(make_engine(settings)) as s:
        ideas = s.exec(select(Idea)).all()
        assert len(ideas) == 10 and all(i.status == "generated" for i in ideas)
        assert len(s.exec(select(Event).where(Event.type == "idea_created")).all()) == 10
        run = s.exec(select(GenerationRun)).one()
        assert run.status == "succeeded" and run.data["requested"] == "default" and run.data["seeds"]


def test_failed_generate_shows_message_and_stores_nothing(make_client, settings):
    def broken(system, prompt, schema):
        raise LLMError("failed", "simulated")

    client = make_client(FakeLLM(broken))
    start(client)
    html = client.post("/challenges/1/generate").text
    assert "The agents couldn't finish" in unescape(html)
    with Session(make_engine(settings)) as s:
        assert s.exec(select(Idea)).all() == []
        assert s.exec(select(GenerationRun)).one().status == "failed"


def test_second_generate_refused_while_running(make_client, settings):
    release = threading.Event()
    entered = threading.Event()

    def slow(system, prompt, schema):
        entered.set()
        release.wait(5)
        return FakeLLM.default_handler(system, prompt, schema)

    client = make_client(FakeLLM(slow))
    start(client)
    first = threading.Thread(target=client.post, args=("/challenges/1/generate",))
    first.start()
    entered.wait(5)
    html = client.post("/challenges/1/generate").text
    release.set()
    first.join(5)
    assert "already working" in html
    with Session(make_engine(settings)) as s:
        assert len(s.exec(select(GenerationRun)).all()) == 1


def test_ideas_survive_restart_and_stuck_runs_are_cleared(make_client, settings):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    with Session(make_engine(settings)) as s:
        s.add(GenerationRun(challenge_id=1, kind="generate", pattern="collaborative"))
        s.commit()

    fresh = make_client()  # a new app on the same data folder = a restart
    assert fresh.get("/challenges/1").text.count('class="card idea"') == 10
    with Session(make_engine(settings)) as s:
        assert {r.status for r in s.exec(select(GenerationRun)).all()} == {"succeeded", "failed"}
