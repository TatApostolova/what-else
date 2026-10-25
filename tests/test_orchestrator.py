import re

import pytest

from whatelse.context import AgentContext
from whatelse.llm import FakeLLM, LLMError
from whatelse.orchestrator import generate, load_techniques, technique_label

CTX = AgentContext("How do I get noticed by teams doing interesting work?", "Some notes.")
KEYS = ["reverse_thinking", "random_associations", "analogies", "scamper", "challenging_assumptions"]
LABELS = {t.key: t.label for t in load_techniques(KEYS)}


def key_of(system):
    return next(k for k in KEYS if f"**{LABELS[k]}**" in system)


def round_of(schema):
    props = schema["properties"]
    return 1 if "seeds" in props else 3 if "pushed" in props else 2


def scripted(round2=None, fail=None, bad=None):
    """Default fake answers, with optional per-(round, technique) overrides.

    round2: {technique: [built_on for draft 1, built_on for draft 2]}
    fail / bad: (round, technique) whose call raises / returns malformed output.
    """

    def handler(system, prompt, schema):
        r, key = round_of(schema), key_of(system)
        if (r, key) == fail:
            raise LLMError("failed", "simulated CLI failure")
        if (r, key) == bad:
            return {"ideas": [{"title": "", "text": "x"}]} if r == 2 else {"nope": True}
        if r == 2 and round2 and key in round2:
            return {"ideas": [{"title": f"{key} draft {i + 1}", "text": "Do a thing.", "built_on": b, "how": "fuses"}
                              for i, b in enumerate(round2[key])]}
        return FakeLLM.default_handler(system, prompt, schema)

    return handler


def calls_in_round(llm, r):
    return [c for c in llm.calls if round_of(c["schema"]) == r]


def test_three_rounds_make_ten_ideas(settings):
    llm = FakeLLM(scripted())
    result = generate(CTX, llm, settings, "collaborative")

    assert [len(calls_in_round(llm, r)) for r in (1, 2, 3)] == [5, 5, 5]
    assert len(result.ideas) == 10
    assert len(result.data["seeds"]) == 15
    assert len(result.data["pushes"]) == 10
    assert all(i.title.startswith("Pushed idea") for i in result.ideas)


def test_round2_attribution_is_worked_out_in_code(settings):
    round2 = {
        "reverse_thinking": [["analogies-1", "scamper-2"], ["random_associations-3", "analogies-2"]],
        # own seed, unknown id and duplicate are all dropped
        "analogies": [["analogies-1", "nonsense-9", "scamper-1", "scamper-1"], []],
    }
    result = generate(CTX, FakeLLM(scripted(round2=round2)), settings, "collaborative")
    drafts = {d["id"]: d for d in result.data["drafts"]}

    assert drafts["reverse_thinking-d1"]["techniques"] == ["reverse_thinking", "analogies", "scamper"]
    assert drafts["reverse_thinking-d1"]["fused_two_techniques"] is True
    assert drafts["analogies-d1"]["built_on"] == ["scamper-1"]
    assert drafts["analogies-d1"]["fused_two_techniques"] is False
    assert drafts["analogies-d2"]["techniques"] == ["analogies"]


def test_prompts_show_only_other_agents_work_and_the_banned_list(settings):
    llm = FakeLLM(scripted())
    generate(CTX, llm, settings, "collaborative")

    scamper_r2 = next(c for c in calls_in_round(llm, 2) if key_of(c["system"]) == "scamper")
    assert "[analogies-1]" in scamper_r2["prompt"]
    assert "[scamper-1]" not in scamper_r2["prompt"]
    assert "Obvious move 1" in scamper_r2["prompt"]
    assert CTX.statement in scamper_r2["prompt"]

    for call in calls_in_round(llm, 3):
        key = key_of(call["system"])
        pushed_ids = re.findall(r"^- \[([^\]]+)\]", call["prompt"], flags=re.M)
        assert len(pushed_ids) == 2
        assert not any(pid.startswith(key + "-") for pid in pushed_ids)


def test_every_draft_pushed_once_and_pusher_added_to_label(settings):
    result = generate(CTX, FakeLLM(scripted()), settings, "collaborative")
    pushed = [p["draft"] for p in result.data["pushes"]]
    assert sorted(pushed) == sorted(d["id"] for d in result.data["drafts"])
    for p in result.data["pushes"]:
        assert not p["draft"].startswith(p["pushed_by"] + "-")
    assert all(len(i.techniques) >= 2 for i in result.ideas)
    assert all("pushed by" in (i.how or "") for i in result.ideas)


def test_failed_round2_call_fails_whole_run(settings):
    with pytest.raises(LLMError):
        generate(CTX, FakeLLM(scripted(fail=(2, "scamper"))), settings, "collaborative")


def test_malformed_round2_output_fails_run(settings):
    with pytest.raises(LLMError) as err:
        generate(CTX, FakeLLM(scripted(bad=(2, "analogies"))), settings, "collaborative")
    assert err.value.kind == "failed"


def test_round1_tolerates_a_single_failed_agent(settings):
    result = generate(CTX, FakeLLM(scripted(fail=(1, "scamper"))), settings, "collaborative")
    assert len(result.ideas) == 10
    assert result.data["round1_failures"][0]["technique"] == "scamper"
    assert not any(s["technique"] == "scamper" for s in result.data["seeds"])


def test_failed_push_keeps_the_drafts(settings):
    result = generate(CTX, FakeLLM(scripted(fail=(3, "analogies"))), settings, "collaborative")
    assert len(result.ideas) == 10
    assert result.data["round3_failures"][0]["technique"] == "analogies"
    assert sum(i.title.startswith("Fake draft") for i in result.ideas) == 2


def test_technique_label():
    techniques = load_techniques(["analogies", "scamper", "reverse_thinking"])
    assert technique_label(["scamper"], techniques) == "SCAMPER"
    assert technique_label(["scamper", "analogies", "reverse_thinking"], techniques) == \
        "SCAMPER ← ANALOGIES + REVERSE THINKING"


def test_api_key_guard(monkeypatch):
    from whatelse.llm import ClaudeCLI

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with pytest.raises(LLMError) as err:
        ClaudeCLI().complete("s", "p", {})
    assert err.value.kind == "api_key"
