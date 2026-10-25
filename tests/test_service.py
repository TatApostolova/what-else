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
