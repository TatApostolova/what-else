import pytest
from sqlmodel import Session, select

from whatelse.db import make_engine
from whatelse.models import Event, GenerationRun, Idea
from whatelse.service import ServiceError, create_challenge, react


@pytest.fixture
def session(settings):
    with Session(make_engine(settings)) as s:
        yield s


def make_idea(session, statement="A challenge"):
    challenge = create_challenge(session, statement, None)
    run = GenerationRun(challenge_id=challenge.id, kind="generate", pattern="collaborative", status="succeeded")
    session.add(run)
    session.flush()
    idea = Idea(challenge_id=challenge.id, run_id=run.id, title="An idea", text="Do it.", techniques=["scamper"])
    session.add(idea)
    session.commit()
    return idea


def events_for(session, idea):
    return session.exec(select(Event).where(Event.idea_id == idea.id).order_by(Event.id)).all()


def test_create_challenge_titles_and_validates(session):
    c = create_challenge(session, "\n  First line here\nmore detail", "  ")
    assert c.title == "First line here" and c.context is None and c.status == "active"
    with pytest.raises(ServiceError):
        create_challenge(session, "   ", "ctx")


def test_save_writes_event_and_status_together(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "save", ["original", "fits_me", "not_a_tag", "original"], "  love it ")
    assert idea.status == "saved"
    (event,) = events_for(session, idea)
    assert (event.type, event.from_status, event.to_status) == ("saved", "generated", "saved")
    assert event.tags == ["original", "fits_me"]  # unknown and duplicate tags dropped, stored as keys
    assert event.note == "love it"


def test_save_with_no_tags_or_note_is_allowed(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "save")
    assert idea.status == "saved" and events_for(session, idea)[0].tags == []


def test_discard_keeps_the_idea(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "discard", ["duplicate"], None)
    assert session.get(Idea, idea.id).status == "discarded"
    assert events_for(session, idea)[0].tags == ["duplicate"]


def test_save_tags_are_not_accepted_on_discard(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "discard", ["original", "too_vague"])
    assert events_for(session, idea)[0].tags == ["too_vague"]


def test_disallowed_transitions_are_refused_without_events(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "discard")
    with pytest.raises(ServiceError):
        react(session, settings, idea.id, "save")
    with pytest.raises(ServiceError):
        react(session, settings, idea.id, "discard")
    assert len(events_for(session, idea)) == 1
    assert session.get(Idea, idea.id).status == "discarded"


def test_saved_idea_can_later_be_discarded(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "save")
    react(session, settings, idea.id, "discard", ["not_practical"], "changed my mind")
    assert [e.to_status for e in events_for(session, idea)] == ["saved", "discarded"]


def test_full_lifecycle_saved_to_completed(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "save", ["practical"])
    react(session, settings, idea.id, "feedback", note="still like it")
    assert idea.status == "saved"
    react(session, settings, idea.id, "action")
    react(session, settings, idea.id, "progress", note="sent two emails")
    react(session, settings, idea.id, "progress", note="one reply")
    react(session, settings, idea.id, "complete", note="got a call", verdict="worked")
    assert (idea.status, idea.verdict) == ("completed", "worked")
    evs = events_for(session, idea)
    assert [e.type for e in evs] == ["saved", "feedback", "actioned", "progress", "progress", "completed"]
    assert evs[-1].data == {"verdict": "worked"} and evs[-1].note == "got a call"


def test_progress_and_feedback_need_a_note(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "save")
    with pytest.raises(ServiceError):
        react(session, settings, idea.id, "feedback", note="  ")
    react(session, settings, idea.id, "action")
    with pytest.raises(ServiceError):
        react(session, settings, idea.id, "progress")


def test_finish_needs_a_valid_verdict(session, settings):
    idea = make_idea(session)
    react(session, settings, idea.id, "save")
    react(session, settings, idea.id, "action")
    for bad in (None, "", "great"):
        with pytest.raises(ServiceError):
            react(session, settings, idea.id, "complete", verdict=bad)
    react(session, settings, idea.id, "complete", verdict="dropped")
    assert idea.status == "completed"  # dropped is a verdict, not a discard


def test_lifecycle_order_is_enforced(session, settings):
    idea = make_idea(session)
    for action in ("action", "progress", "complete"):
        with pytest.raises(ServiceError):
            react(session, settings, idea.id, action, note="x", verdict="worked")
    react(session, settings, idea.id, "save")
    react(session, settings, idea.id, "action")
    react(session, settings, idea.id, "discard", ["not_practical"])  # an experiment can still be discarded
    assert idea.status == "discarded"
    react_ok = [e.type for e in events_for(session, idea)]
    assert react_ok == ["saved", "actioned", "discarded"]


def test_challenge_status_changes_write_events(session):
    from whatelse.service import change_challenge_status

    c = create_challenge(session, "A challenge", None)
    change_challenge_status(session, c.id, "pause", note="ignored for pause")
    assert (c.status, c.outcome_note) == ("paused", None)
    change_challenge_status(session, c.id, "reopen")
    change_challenge_status(session, c.id, "achieve", note="got there")
    assert (c.status, c.outcome_note) == ("achieved", "got there")
    with pytest.raises(ServiceError):
        change_challenge_status(session, c.id, "pause")  # closed challenges must be reopened first
    change_challenge_status(session, c.id, "reopen")
    assert (c.status, c.outcome_note) == ("active", None)
    statuses = session.exec(select(Event).where(Event.type == "challenge_status").order_by(Event.id)).all()
    assert [(e.from_status, e.to_status) for e in statuses] == [
        ("active", "paused"), ("paused", "active"), ("active", "achieved"), ("achieved", "active")]
    assert statuses[2].note == "got there"


def test_closed_challenge_refuses_changes(session, settings):
    from whatelse.service import add_own_idea, change_challenge_status, edit_challenge

    idea = make_idea(session)
    change_challenge_status(session, idea.challenge_id, "abandon")
    for attempt in (
        lambda: react(session, settings, idea.id, "save"),
        lambda: edit_challenge(session, idea.challenge_id, "new", None),
        lambda: add_own_idea(session, idea.challenge_id, "mine", None),
    ):
        with pytest.raises(ServiceError, match="Reopen it"):
            attempt()
    change_challenge_status(session, idea.challenge_id, "reopen")
    react(session, settings, idea.id, "save")
    assert idea.status == "saved"
