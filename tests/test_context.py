import pytest
from sqlmodel import Session, select

from whatelse.context import build_context
from whatelse.db import make_engine
from whatelse.llm import FakeLLM, LLMError
from whatelse.models import Event, GenerationRun, Idea
from whatelse.orchestrator import run_generate, run_rework
from whatelse.patterns import challenge_block
from whatelse.service import ServiceError, create_challenge, react


@pytest.fixture
def engine(settings):
    return make_engine(settings)


def add_ideas(engine, challenge_id, titles):
    with Session(engine) as s:
        run = GenerationRun(challenge_id=challenge_id, kind="generate", pattern="collaborative", status="succeeded")
        s.add(run)
        s.flush()
        ideas = [Idea(challenge_id=challenge_id, run_id=run.id, title=t, text=f"Text of {t}.",
                      techniques=["scamper"]) for t in titles]
        s.add_all(ideas)
        s.commit()
        return [i.id for i in ideas]


def new_challenge(engine, statement="Challenge A", context="Context A"):
    with Session(engine) as s:
        return create_challenge(s, statement, context).id


def test_empty_history_for_a_fresh_challenge(engine, settings):
    cid = new_challenge(engine)
    with Session(engine) as s:
        ctx = build_context(s, cid, settings.tag_labels)
    assert (ctx.statement, ctx.context, ctx.history) == ("Challenge A", "Context A", "")
    assert "What has happened" not in challenge_block(ctx)


def test_history_has_each_section_with_reasons(engine, settings):
    cid = new_challenge(engine)
    liked, rejected, pending, tried = add_ideas(engine, cid, ["Liked one", "Rejected one", "Pending one", "Tried one"])
    with Session(engine) as s:
        react(s, settings, liked, "save", ["fits_me"], "my kind of thing")
        react(s, settings, rejected, "discard", ["already_tried", "too_much_work"], "did this last year")
        react(s, settings, tried, "save")
        idea = s.get(Idea, tried)
        idea.status, idea.verdict = "completed", "worked"
        s.add(idea)
        s.add(Event(challenge_id=cid, idea_id=tried, type="progress", note="sent three emails"))
        s.add(Event(challenge_id=cid, idea_id=tried, type="completed", note="got two replies",
                    from_status="actioned", to_status="completed"))
        s.commit()
        history = build_context(s, cid, settings.tag_labels).history

    liked_part = history.split("### Liked")[1].split("###")[0]
    assert '"Liked one"' in liked_part and "fits me" in liked_part and "my kind of thing" in liked_part
    rejected_part = history.split("### Rejected")[1].split("###")[0]
    assert "already tried, too much work" in rejected_part and "did this last year" in rejected_part
    tried_part = history.split("### Tried")[1].split("###")[0]
    assert "sent three emails" in tried_part and "Worked" in tried_part and "got two replies" in tried_part
    pending_part = history.split("### Already suggested")[1]
    assert '- "Pending one"' in pending_part and "Text of Pending one" not in pending_part


def test_history_reaches_the_agent_prompts(engine, settings):
    cid = new_challenge(engine)
    (first,) = add_ideas(engine, cid, ["Old idea"])
    with Session(engine) as s:
        react(s, settings, first, "discard", ["not_me"])
    llm = FakeLLM()
    run_generate(engine, cid, llm, settings)
    assert all("Old idea" in c["prompt"] and "Do not repeat rejected ideas" in c["prompt"] for c in llm.calls)


def test_challenges_never_share_history(engine, settings):
    a = new_challenge(engine, "Challenge A")
    b = new_challenge(engine, "Challenge B")
    (idea_a,) = add_ideas(engine, a, ["Only in A"])
    with Session(engine) as s:
        react(s, settings, idea_a, "save", ["original"])
        assert build_context(s, b, settings.tag_labels).history == ""
        assert "Only in A" in build_context(s, a, settings.tag_labels).history


def test_history_is_capped(engine, settings):
    cid = new_challenge(engine)
    add_ideas(engine, cid, [f"Idea {i}" for i in range(60)])
    with Session(engine) as s:
        history = build_context(s, cid).history
    assert history.count('\n- "') + history.startswith("- ") <= 40


def test_rework_creates_linked_idea_and_records_the_note(engine, settings):
    cid = new_challenge(engine)
    (orig,) = add_ideas(engine, cid, ["Big idea"])
    llm = FakeLLM()
    new = run_rework(engine, orig, "make it smaller", llm, settings)
    with Session(engine) as s:
        original = s.get(Idea, orig)
        assert original.status == "reworked" and new.parent_idea_id == orig and new.status == "generated"
        history = build_context(s, cid).history
    assert '"Big idea" — asked to change: "make it smaller" → became "Fake reworked idea"' in history
    assert "make it smaller" in llm.calls[0]["prompt"] and "Big idea" in llm.calls[0]["prompt"]
    assert "**SCAMPER**" in llm.calls[0]["system"]  # the original's own technique leads


def test_rework_of_a_saved_idea_keeps_it_saved(engine, settings):
    cid = new_challenge(engine)
    (orig,) = add_ideas(engine, cid, ["Liked idea"])
    with Session(engine) as s:
        react(s, settings, orig, "save")
    run_rework(engine, orig, "a cheaper version", FakeLLM(), settings)
    with Session(engine) as s:
        assert s.get(Idea, orig).status == "saved"


def test_failed_rework_leaves_the_original_untouched(engine, settings):
    cid = new_challenge(engine)
    (orig,) = add_ideas(engine, cid, ["Fragile idea"])

    def broken(*_):
        raise LLMError("failed", "simulated")

    with pytest.raises(LLMError):
        run_rework(engine, orig, "change it", FakeLLM(broken), settings)
    with Session(engine) as s:
        assert s.get(Idea, orig).status == "generated"
        assert len(s.exec(select(Idea)).all()) == 1


def test_rework_needs_a_note(engine, settings):
    cid = new_challenge(engine)
    (orig,) = add_ideas(engine, cid, ["Idea"])
    llm = FakeLLM()
    with pytest.raises(ServiceError):
        run_rework(engine, orig, "   ", llm, settings)
    assert llm.calls == []
