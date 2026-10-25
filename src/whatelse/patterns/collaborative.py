"""Default pattern: diverge, cross-pollinate, push.

Round 1 (diverge): every technique names the obvious moves (a shared banned list)
  and proposes wild seeds.
Round 2 (cross-pollinate): every technique sees the *other* techniques' seeds and makes
  `ideas_per_agent` ideas, each fusing seeds from at least two other techniques.
Round 3 (push): every technique takes drafts made by other agents and pushes them
  further; the pushed version replaces the draft.
All calls in a round run in parallel. Attribution is worked out here from ids,
never trusted from the model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from whatelse.patterns import (
    IdeaDraft,
    PatternResult,
    as_llm_error,
    challenge_block,
    render,
    run_parallel,
    system_prompt,
)

NAME = "collaborative"
OBVIOUS_PER_AGENT = 3
BANNED_CAP = 15


class _SeedIn(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)


class _Round1Out(BaseModel):
    obvious: list[str] = Field(default_factory=list)
    seeds: list[_SeedIn] = Field(min_length=1)


class _DraftIn(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    built_on: list[str] = Field(default_factory=list)
    how: str = ""


class _Round2Out(BaseModel):
    ideas: list[_DraftIn] = Field(min_length=1)


class _PushIn(BaseModel):
    id: str = ""
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    how: str = ""


class _Round3Out(BaseModel):
    pushed: list[_PushIn] = Field(min_length=1)


def _array(items: dict, n: int | None = None, min_items: int | None = None) -> dict:
    schema: dict = {"type": "array", "items": items}
    if n is not None:
        schema["minItems"] = schema["maxItems"] = n
    elif min_items is not None:
        schema["minItems"] = min_items
    return schema


def _object(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


STR = {"type": "string"}


def round1_schema(n: int) -> dict:
    return _object({
        "obvious": _array(STR, OBVIOUS_PER_AGENT),
        "seeds": _array(_object({"title": STR, "text": STR}), n),
    })


def round2_schema(k: int) -> dict:
    return _object({
        "ideas": _array(_object({"title": STR, "text": STR, "built_on": _array(STR, min_items=2), "how": STR}), k),
    })


def round3_schema(k: int) -> dict:
    return _object({"pushed": _array(_object({"id": STR, "title": STR, "text": STR, "how": STR}), k)})


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines) or "- (none)"


def run(ctx, llm, techniques, settings) -> PatternResult:
    block = challenge_block(ctx)
    labels = {t.key: t.label for t in techniques}
    n = settings.seeds_per_agent
    k = settings.ideas_per_agent

    # ---- Round 1: diverge ---------------------------------------------------
    def round1(t):
        out = llm.complete(
            system_prompt(t),
            render("collab_round1", challenge=block, label=t.label, n=n, obvious_n=OBVIOUS_PER_AGENT),
            round1_schema(n),
        )
        return _Round1Out.model_validate(out)

    seeds: dict[str, dict] = {}
    banned: list[str] = []
    round1_failures = []
    for t, res in run_parallel(round1, techniques):
        if isinstance(res, Exception):
            round1_failures.append((t.key, as_llm_error(res)))
            continue
        for i, s in enumerate(res.seeds, start=1):
            seeds[f"{t.key}-{i}"] = {"id": f"{t.key}-{i}", "technique": t.key, "title": s.title, "text": s.text}
        for move in res.obvious:
            if move.strip() and move.strip().lower() not in {b.lower() for b in banned}:
                banned.append(move.strip())
    banned = banned[:BANNED_CAP]

    if len({s["technique"] for s in seeds.values()}) < 2:
        if round1_failures:
            raise round1_failures[0][1]
        raise as_llm_error(RuntimeError("round 1 produced seeds from fewer than two techniques"))

    # ---- Round 2: cross-pollinate --------------------------------------------
    def round2(t):
        others = [s for s in seeds.values() if s["technique"] != t.key]
        seed_lines = "\n".join(
            f"- [{s['id']}] ({labels[s['technique']]}) {s['title']}: {s['text']}" for s in others
        )
        out = llm.complete(
            system_prompt(t),
            render("collab_round2", challenge=block, banned=_bullets(banned), seeds=seed_lines, label=t.label, k=k),
            round2_schema(k),
        )
        allowed = {s["id"] for s in others}
        drafts = []
        for i, d in enumerate(_Round2Out.model_validate(out).ideas[:k], start=1):
            built_on = [sid for sid in dict.fromkeys(d.built_on) if sid in allowed]
            techs = [t.key]
            for sid in built_on:
                if seeds[sid]["technique"] not in techs:
                    techs.append(seeds[sid]["technique"])
            drafts.append({
                "id": f"{t.key}-d{i}",
                "author": t.key,
                "title": d.title.strip(),
                "text": d.text.strip(),
                "techniques": techs,
                "built_on": built_on,
                "how": d.how.strip() if built_on else "",
                "fused_two_techniques": len(techs) >= 3,
            })
        return drafts

    drafts: list[dict] = []
    for t, res in run_parallel(round2, techniques):
        if isinstance(res, Exception):
            raise as_llm_error(res)  # no partial runs
        drafts.extend(res)

    # ---- Round 3: push -------------------------------------------------------
    assignments = _assign_pushes(techniques, drafts)

    def round3(t):
        mine = assignments[t.key]
        if not mine:
            return []
        draft_lines = "\n".join(
            f"- [{d['id']}] {d['title']}: {d['text']}" for d in mine
        )
        out = llm.complete(
            system_prompt(t),
            render("collab_round3", challenge=block, banned=_bullets(banned), drafts=draft_lines, label=t.label),
            round3_schema(len(mine)),
        )
        pushed = _Round3Out.model_validate(out).pushed
        by_id = {p.id: p for p in pushed}
        # Match by id; fall back to order if the model mangled an id.
        return [(d, by_id.get(d["id"]) or (pushed[i] if i < len(pushed) else None)) for i, d in enumerate(mine)]

    final: dict[str, IdeaDraft] = {}
    round3_log = []
    round3_failures = []
    for t, res in run_parallel(round3, techniques):
        if isinstance(res, Exception):
            # A failed push keeps those drafts as they were: the ideas are complete either way.
            round3_failures.append({"technique": t.key, "error": str(as_llm_error(res))})
            continue
        for draft, push in res:
            if push is None:
                continue
            techs = draft["techniques"] + ([t.key] if t.key not in draft["techniques"] else [])
            how_parts = [draft["how"], f"pushed by {labels[t.key]}: {push.how.strip()}" if push.how.strip()
                         else f"pushed by {labels[t.key]}"]
            final[draft["id"]] = IdeaDraft(
                title=push.title.strip(),
                text=push.text.strip(),
                techniques=techs,
                built_on=draft["built_on"],
                how="; ".join(p for p in how_parts if p) or None,
            )
            round3_log.append({"draft": draft["id"], "pushed_by": t.key, "title": push.title, "text": push.text,
                               "how": push.how})

    ideas = [
        final.get(d["id"]) or IdeaDraft(
            title=d["title"], text=d["text"], techniques=d["techniques"],
            built_on=d["built_on"], how=d["how"] or None,
        )
        for d in drafts
    ]

    return PatternResult(
        pattern=NAME,
        ideas=ideas,
        data={
            "banned": banned,
            "seeds": list(seeds.values()),
            "drafts": drafts,
            "pushes": round3_log,
            "round1_failures": [{"technique": key, "error": str(e)} for key, e in round1_failures],
            "round3_failures": round3_failures,
        },
    )


def _assign_pushes(techniques, drafts: list[dict]) -> dict[str, list[dict]]:
    """Give every draft to exactly one *other* agent, spreading the load evenly.

    Agent i pushes the j-th draft of agent i+j (mod n), so no one pushes their own
    work and each draft is pushed once.
    """
    keys = [t.key for t in techniques]
    by_author: dict[str, list[dict]] = {key: [d for d in drafts if d["author"] == key] for key in keys}
    assignments: dict[str, list[dict]] = {key: [] for key in keys}
    if len(keys) < 2:
        return assignments
    for a, author in enumerate(keys):
        for j, draft in enumerate(by_author[author]):
            offset = (j % (len(keys) - 1)) + 1
            pusher = keys[(a - offset) % len(keys)]
            assignments[pusher].append(draft)
    return assignments
