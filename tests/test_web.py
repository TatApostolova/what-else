import re
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


def test_save_and_discard_from_explore(make_client, settings):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")

    panel = client.get("/ideas/1/panel/save?tab=explore").text
    assert "What do you like about it?" in panel and 'value="fits_me"' in panel
    assert "same as another idea" in client.get("/ideas/2/panel/discard").text

    html = client.post("/ideas/1/save", data={"tags": ["original", "practical"], "note": "nice", "tab": "explore"}).text
    assert 'id="idea-1"' not in html  # left Explore
    assert 'Idea Library <span class="count">1</span>' in html
    client.post("/ideas/2/discard", data={"tags": ["duplicate"], "tab": "explore"})

    explore = client.get("/challenges/1").text
    assert explore.count('class="card idea"') == 8
    library = client.get("/challenges/1?tab=library").text
    assert 'id="idea-1"' in library and "Saved because:" in library and "nice" in library
    assert 'id="idea-2"' not in library


def test_two_tap_save_without_note(make_client, settings):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    client.post("/ideas/3/save", data={"tab": "explore"})  # panel submit with nothing chosen
    with Session(make_engine(settings)) as s:
        assert s.get(Idea, 3).status == "saved"


def test_unreacted_ideas_stay_after_another_generate(make_client):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    client.post("/ideas/1/discard", data={"tab": "explore"})
    html = client.post("/challenges/1/generate").text
    assert html.count('class="card idea"') == 19
    assert 'id="idea-2"' in html and 'id="idea-1"' not in html


def test_rework_from_explore_shows_lineage(make_client, settings):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    assert "What should change?" in client.get("/ideas/1/panel/rework").text
    html = client.post("/ideas/1/rework", data={"note": "make it cheaper", "tab": "explore"}).text
    assert 'id="idea-1"' not in html and 'id="idea-11"' in html
    assert "Reworked from: Pushed idea" in html


def test_rework_without_note_shows_message(make_client):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    html = unescape(client.post("/ideas/1/rework", data={"note": "", "tab": "explore"}).text)
    assert "Say what you'd like changed" in html and 'id="idea-1"' in html


def test_edit_challenge_changes_next_generate(make_client, settings):
    llm = FakeLLM()
    client = make_client(llm)
    start(client, context="old context")
    resp = client.post("/challenges/1/edit", data={"statement": "A new framing", "context": "new context"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert "A new framing" in client.get("/challenges/1").text
    client.post("/challenges/1/generate")
    assert "new context" in llm.calls[0]["prompt"] and "old context" not in llm.calls[0]["prompt"]
    with Session(make_engine(settings)) as s:
        edit_event = s.exec(select(Event).where(Event.type == "context_edited")).one()
        assert edit_event.data["previous_context"] == "old context"


def test_library_to_experiments_flow(make_client, settings):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    client.post("/ideas/1/save", data={"tags": ["practical"], "tab": "explore"})

    library = client.get("/challenges/1?tab=library").text
    assert "Move to Action" in library and "Add feedback" in library and "History" in library
    assert "Any new thoughts" in client.get("/ideas/1/panel/feedback?tab=library").text
    client.post("/ideas/1/feedback", data={"note": "worth a go", "tab": "library"})
    assert "worth a go" in client.get("/challenges/1?tab=library").text

    html = client.post("/ideas/1/action", data={"tab": "library"}).text
    assert 'Experiments <span class="count">1</span>' in html and 'id="idea-1"' not in html

    client.post("/ideas/1/progress", data={"note": "first email sent", "tab": "experiments"})
    client.post("/ideas/1/progress", data={"note": "second email sent", "tab": "experiments"})
    exp = client.get("/challenges/1?tab=experiments").text
    assert "Running" in exp and exp.index("first email sent") < exp.index("second email sent")

    panel = client.get("/ideas/1/panel/complete?tab=experiments").text
    assert 'value="didnt_work"' in panel and "Partly worked" in panel
    done = unescape(client.post("/ideas/1/complete",
                                data={"verdict": "worked", "note": "landed a meeting", "tab": "experiments"}).text)
    assert "Finished: Worked" in done and "Log progress" not in done


def test_experiments_running_before_finished(make_client):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    for i in (1, 2):
        client.post(f"/ideas/{i}/save", data={"tab": "explore"})
        client.post(f"/ideas/{i}/action", data={"tab": "library"})
    client.post("/ideas/1/complete", data={"verdict": "partly", "tab": "experiments"})
    exp = client.get("/challenges/1?tab=experiments").text
    assert exp.index('id="idea-2"') < exp.index('id="idea-1"')


def test_verdict_reaches_the_next_generate(make_client):
    llm = FakeLLM()
    client = make_client(llm)
    start(client)
    client.post("/challenges/1/generate")
    client.post("/ideas/1/save", data={"tab": "explore"})
    client.post("/ideas/1/action", data={"tab": "library"})
    client.post("/ideas/1/complete", data={"verdict": "didnt_work", "note": "nobody replied", "tab": "experiments"})
    llm.calls.clear()
    client.post("/challenges/1/generate")
    assert "Didn't work" in llm.calls[0]["prompt"] and "nobody replied" in llm.calls[0]["prompt"]


def test_add_own_idea_goes_to_library_and_reaches_agents(make_client, settings):
    llm = FakeLLM()
    client = make_client(llm)
    start(client)
    html = client.post("/challenges/1/ideas", data={"title": "Host a skills swap", "text": "Trade lessons."}).text
    assert 'Idea Library <span class="count">1</span>' in html and "YOUR IDEA" in html and "Host a skills swap" in html
    assert "Move to Action" in html

    blank = unescape(client.post("/challenges/1/ideas", data={"title": "  ", "text": "x"}).text)
    assert "Give your idea a short title" in blank

    client.post("/challenges/1/generate")
    assert "Host a skills swap\" (the person's own idea)" in llm.calls[0]["prompt"]


def test_rework_of_own_idea_credits_both(make_client):
    client = make_client()
    start(client)
    client.post("/challenges/1/ideas", data={"title": "My plan", "text": ""})
    html = client.post("/ideas/1/rework", data={"note": "make it bolder", "tab": "library"}).text
    assert "Reworked from: My plan" in client.get("/challenges/1").text
    explore = client.get("/challenges/1").text
    assert "REVERSE THINKING ← YOUR IDEA" in explore


def test_close_shows_summary_with_correct_counts(make_client):
    client = make_client()
    start(client)
    client.post("/challenges/1/generate")
    client.post("/ideas/1/save", data={"tab": "explore"})
    client.post("/ideas/2/save", data={"tab": "explore"})
    client.post("/ideas/3/discard", data={"tab": "explore"})
    client.post("/ideas/4/rework", data={"note": "smaller", "tab": "explore"})
    client.post("/ideas/1/action", data={"tab": "library"})
    client.post("/ideas/1/complete", data={"verdict": "worked", "tab": "experiments"})
    client.post("/challenges/1/ideas", data={"title": "Mine"})

    resp = client.post("/challenges/1/status", data={"action": "achieve", "note": "found a way in"},
                       follow_redirects=False)
    assert resp.headers["location"] == "/challenges/1?tab=summary"
    page = unescape(client.get("/challenges/1").text)  # closed challenges open on the Summary
    assert "found a way in" in page and 'class="tabs"' in page
    stats = dict(re.findall(r"<dt>([^<]+)</dt><dd>(\d+)</dd>", page))
    assert stats == {"Generated": "11", "Your own": "1", "Saved": "3", "Discarded": "1", "Reworked": "1",
                     "Actioned": "1", "Finished": "1"}
    assert "Worked" in page and "Mine" in page


def test_closed_challenge_is_read_only_until_reopened(make_client, settings):
    llm = FakeLLM()
    client = make_client(llm)
    start(client)
    client.post("/challenges/1/generate")
    client.post("/challenges/1/status", data={"action": "pause"})
    page = client.get("/challenges/1").text
    assert "Reopen challenge" in page and "Generate</button>" not in page and "panel/save" not in page

    calls = len(llm.calls)
    html = unescape(client.post("/challenges/1/generate").text)
    assert "This challenge is paused" in html and len(llm.calls) == calls
    assert "Reopen it" in unescape(client.post("/ideas/1/save", data={"tab": "explore"}).text)
    with Session(make_engine(settings)) as s:
        assert s.get(Idea, 1).status == "generated"

    client.post("/challenges/1/status", data={"action": "reopen"})
    page = client.get("/challenges/1").text
    assert "Generate</button>" in page and "panel/save" in page and page.count('class="card idea"') == 10


def test_dashboard_orders_active_paused_closed(make_client):
    client = make_client()
    for name in ("Closed one", "Paused one", "Active one"):
        start(client, statement=name)
    client.post("/challenges/1/status", data={"action": "abandon"})
    client.post("/challenges/2/status", data={"action": "pause"})
    client.post("/challenges/3/generate")
    page = client.get("/").text
    assert page.index("Active one") < page.index("Paused one") < page.index("Closed one")
    assert "10 ideas" in page and "Abandoned" in page


def test_delete_challenge_removes_everything(make_client, settings):
    import json

    client = make_client()
    start(client, statement="Keep me")
    start(client, statement="Delete me please", context="secret context")
    client.post("/challenges/2/generate")
    client.post("/ideas/1/save", data={"tab": "explore"})
    client.post("/challenges/2/edit", data={"statement": "Delete me, edited", "context": ""})
    log = settings.log_path
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps({"prompt": p}) for p in
                             ["...Delete me please...", "...Delete me, edited...", "...Keep me..."]) + "\n",
                   encoding="utf-8")

    assert "Delete challenge" in client.get("/challenges/2").text
    assert client.post("/challenges/2/delete", data={}).status_code == 400  # must be confirmed
    resp = client.post("/challenges/2/delete", data={"confirm": "yes"}, follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/"

    assert client.get("/challenges/2").status_code == 404
    assert "Delete me" not in client.get("/").text and "Keep me" in client.get("/").text
    with Session(make_engine(settings)) as s:
        for model in (Idea, Event, GenerationRun):
            assert s.exec(select(model).where(model.challenge_id == 2)).all() == []
        assert s.exec(select(Event).where(Event.challenge_id == 1)).all()  # other challenge untouched
    assert [json.loads(l)["prompt"] for l in log.read_text(encoding="utf-8").splitlines()] == ["...Keep me..."]
