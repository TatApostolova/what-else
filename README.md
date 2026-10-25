# What Else?

A small creative studio where five AI agents, each thinking with a different creative technique, work together to find unconventional ideas for a challenge you describe. You react to each idea (save, discard, rework), try the promising ones, and record what worked. The agents read that history next time, so each round builds on the last. When the challenge is done, you close it and get a summary.

Built for the Devpost **Build With AI: Basics** hackathon.

## Try it

**Hosted sample (no account needed):** https://what-else-demo.onrender.com

The hosted version runs in **sample mode**: a fictional challenge (a small bookshop looking for new ways to bring people in) with agent answers recorded earlier from real runs. Everything else is live, including Save / Discard / Rework, the Idea Library, Experiments, the dashboard and the closing summary. **Reset demo** in the banner restores the starting state. It's on a free plan that sleeps when idle, so the first load can take about a minute.

To use the live agents on your own challenge, run it locally (below).

## How it works

- **Five techniques, five agents.** Reverse Thinking, Random Associations, Analogies, SCAMPER and Challenging Assumptions. Each is a plain text file in `src/whatelse/techniques/`.
- **Three rounds per Generate.** *Diverge:* each agent names the obvious moves (these become a shared banned list) and proposes wild seeds. *Cross-pollinate:* each agent sees the other agents' seeds and builds ideas that fuse at least two other techniques. *Push:* each agent takes ideas from the others and pushes them further. That gives ten ideas, each labelled with every technique that shaped it.
- **It learns from you.** Every reaction is stored as a timestamped event with reason tags. The next Generate passes a summary of what you saved, discarded, reworked and tested to the agents.
- **Built to finish.** A challenge can be paused, achieved or abandoned. The closing summary is built from your own history with no AI call.

Stack: Python, FastAPI, Jinja2 + HTMX, SQLite via SQLModel. Agents run through the Claude Code CLI in headless mode (`claude -p`) on an existing Claude subscription, with no API key. No JavaScript framework, no build step.

## Run it locally

Requirements: Python 3.12+ and the [Claude Code CLI](https://code.claude.com/docs/en/overview), logged in with a claude.ai subscription. Make sure `ANTHROPIC_API_KEY` is **not** set, or calls will be billed to the API.

```
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m whatelse
```

This opens http://127.0.0.1:8000. On Windows you can also double-click `What Else.cmd`. Your data stays in a local SQLite file outside the repository.

- **Sample mode locally:** set `WHATELSE_MODE=demo` before `python -m whatelse`.
- **Tests:** `pytest` (uses a fake LLM and a temporary database, never calls Claude).
- **Re-recording the sample:** `python tools/record_demo.py` (uses your Claude Code login).

## How it was built

Planned and built with Claude Code, using the hackathon's skills in order: `1-start` → `2-scope` → `3-prd` → `4-spec` → `5-build`. The planning documents are in [`devpost/`](devpost/): [scope](devpost/scope.md), [PRD](devpost/prd.md), [spec](devpost/spec.md) and an [app map](devpost/app-map.html).

A few deliberate design choices: a single reading column so each idea gets full attention, the technique labels in the corner of every card so you can see which ways of thinking produced it, and one teal accent on a warm off-white page.
