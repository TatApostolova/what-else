---
doc: spec
status: approved
---

# What Else? — Technical Spec

## How This Works, In Plain Language

What Else? is a small web app that runs on your own computer. Every part is plain Python except the agents.

- **The server** is a Python program (FastAPI) that waits for the browser to ask for a page or press a button, and answers with ready-made HTML. Typing `python -m whatelse` starts it and opens your browser.
- **The pages** are HTML templates (Jinja2) with a small helper library (HTMX) that lets a button update one part of the page, such as the Explore list, without reloading the whole page. There's no JavaScript framework and no build step.
- **The database** is one SQLite file on your machine, like a spreadsheet the program reads and writes. Your real database and the demo database are two separate files, and neither is ever in the repository.
- **The event log:** every reaction (save, discard, rework, feedback, progress, verdict, close, reopen) is written as a new, timestamped row with its reason tags. Rows are never edited or deleted, so the full history of every idea and challenge is always there.
- **The agents:** each creative technique is a text file describing how that agent thinks. When you press Generate, the app runs Claude Code in headless mode (`claude -p`) once per agent, on your existing subscription with no API key. In round 1 (diverge) each agent names the obvious moves, which become a shared banned list, and proposes wild seeds. In round 2 (cross-pollinate) each agent sees all the *other* agents' seeds and makes two ideas, each fusing seeds from at least two other techniques. In round 3 (push) each agent takes two ideas made by other agents and pushes them further with its own technique. That gives ten ideas, each labelled with every technique that contributed to it.
- **The context builder** is one Python file that decides what history the agents see: the challenge, your context, and a summary of what you saved, discarded, reworked and tested. It's the only place that does this, so a smarter analysis layer can replace it later.
- **The LLM adapter** is one Python file that knows how to call Claude. Nothing else in the app does. Swapping in an API key or another provider later means changing only this file.

Why this shape: one process, one file database, no accounts, no cloud services and no paid API. The only hard part, the agents, sits behind two small boundaries (adapter and context builder), so everything else can stay simple.

## The Core Journey Through the System
PRD ref: `prd.md > The Core Journey`.

1. **Arrive.** The browser asks for `/`. The server counts challenges in the database: with none, it shows the welcome page, and otherwise the dashboard.
2. **Start a challenge.** The form posts to `/challenges`. The server saves a `Challenge` row (status `active`) and a `challenge_created` event, then redirects to `/challenges/{id}` (Explore tab).
3. **Generate.** HTMX posts to `/challenges/{id}/generate`. The server:
   1. refuses if a run is already `running` for this challenge;
   2. creates a `GenerationRun` (status `running`);
   3. asks `context.py` for the agent context (statement, context, history summary);
   4. hands it to `orchestrator.py`, which loads the configured pattern and the five technique definitions;
   5. the pattern makes its `claude -p` calls through `llm.py` (three rounds of 5 parallel calls each);
   6. each returned idea is checked by Pydantic and stored as an `Idea` (status `generated`) with an `idea_created` event;
   7. the run is marked `succeeded` and the new cards are returned as HTML into the Explore list.
   The browser shows "The agents are working…" until the response arrives.
4. **React.** Each card's Save / Discard / Rework opens an inline panel. Submitting posts to `/ideas/{id}/save` (or `/discard`, `/rework`). The server writes an event with tags and note, updates the idea's status, and returns the updated tab contents. For Rework, `orchestrator.py` makes one call with the original idea, the note and the context. The new `Idea` gets `parent_idea_id` and appears in Explore.
5. **Idea Library and Experiments.** Same pattern: `/ideas/{id}/action`, `/feedback`, `/progress`, `/complete`. Each is one event plus a status change.
6. **Generate again.** `context.py` now reads this challenge's events, so the agents see the new history.
7. **Finish.** `/challenges/{id}/status` posts `pause`, `achieve`, `abandon` or `reopen`. It writes the event and updates the status. `summary.py` builds the closing summary from the stored rows with ordinary queries and no AI call.

```
Browser (HTMX) ──HTTP──▶ FastAPI routes ──▶ SQLModel ──▶ SQLite file
                               │
                               ▼
                       orchestrator.py ◀── context.py (reads events)
                         │    loads techniques/*.md, patterns/*.py
                         ▼
                       llm.py ──subprocess──▶ claude -p (subscription)
```

## Stack

| Piece | Choice | Docs |
|---|---|---|
| Language | Python **3.14** (already installed; verified compatible 2026-10-19) | https://docs.python.org/3.14/ |
| Environment | standard `venv` + `pip`, project defined in `pyproject.toml` (installed with `pip install -e ".[dev]"`) | https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ |
| Web server | FastAPI 0.146 + Uvicorn 0.54 | https://fastapi.tiangolo.com/ · https://www.uvicorn.org/ |
| Templates | Jinja2 3.1 | https://jinja.palletsprojects.com/ |
| Partial page updates | HTMX 2.x, vendored as one file in `static/` (works offline) | https://htmx.org/docs/ |
| Database | SQLite through SQLModel 0.0.48 (on SQLAlchemy 2.1), with Pydantic 2.14 for validation | https://sqlmodel.tiangolo.com/ · https://docs.pydantic.dev/ |
| Form parsing | python-multipart | https://github.com/Kludex/python-multipart |
| Config | `tomllib` (standard library) for `config.toml` | https://docs.python.org/3.14/library/tomllib.html |
| Agents | Claude Code CLI 2.1.x in headless mode (`claude -p`) | https://code.claude.com/docs/en/headless |
| Tests | pytest 9 + FastAPI TestClient (install `httpx2`, as recent Starlette warns that `httpx` is deprecated) | https://docs.pytest.org/ |

Rationale: the stack was agreed in `scope.md > Technical Direction`. You chose to **use the installed Python 3.14 instead of installing uv and 3.12**, after the agent verified on 2026-10-19 that every dependency installs and runs on 3.14 (a SQLModel table round-trip and a FastAPI route both worked).

## Where It Runs and How Someone Tries It

- **Runtime:** a local process on Windows, which also works on macOS/Linux. Requirements: Python 3.14 and the Claude Code CLI logged in with a claude.ai subscription. `ANTHROPIC_API_KEY` must **not** be set, otherwise calls are billed to the API.
- **First-time setup:**
  ```
  python -m venv .venv
  .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
  pip install -e ".[dev]"
  ```
- **Run for real use:** `python -m whatelse` starts the server on http://127.0.0.1:8000 and opens the browser. Data goes to the private data folder (see `Data Model > Where data lives`).
- **Open without a terminal (Windows):** double-click `What Else.cmd` in the project folder, or a desktop shortcut to it. It activates `.venv` and runs `python -m whatelse` in a minimised console window. Closing that window stops the app. If the app is already running (port 8000 answers), `__main__.py` just opens the browser at http://127.0.0.1:8000 instead of starting a second server. Once the app is running, http://127.0.0.1:8000 can also be bookmarked. Added after spec approval, at your request.
- **Run for the demo video:** `python -m whatelse --demo` (or `WHATELSE_MODE=demo`). This uses a separate `demo.db`, seeded from `demo/seed.json` (a fictional persona's challenge) on first start, and shows a "Demo" badge.
- **Reset the demo:** `python -m whatelse --demo --reset-demo` deletes and re-seeds only `demo.db`.
- **Tests:** `pytest`. Tests use a fake LLM and a temporary database, so they never call Claude.
- **Submission:** a short demo video recorded in demo mode, plus the public GitHub repository. No deployment: the app relies on the user's own Claude Code login, so a hosted version would need a different provider (see `scope.md > Later`).

## Look and Feel
Carries forward `prd.md > Look and Feel` and `scope.md > Inspiration & Identity`. All styling lives in one hand-written `static/style.css`, with no CSS framework.

- **Palette (CSS variables):** page `#f7f7f5` (warm off-white), cards `#ffffff` with a 1px border `#e7e5e4` and a soft shadow, text `#1c1917`, muted text `#78716c`. One accent, deep teal `#0f766e`, used for links, focus rings, the selected tab and selected tag chips. Save is a dark filled button (`#1c1917`, white text). Discard is outlined. Rework is a text-style button in the accent colour.
- **Status badges:** small rounded pills. Active is teal, Paused amber, Achieved green, Abandoned grey. For ideas: Saved, Actioned, Completed plus the verdict (Worked green / Partly amber / Didn't work grey / Dropped outline).
- **Type:** system sans-serif stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`). Idea titles about 1.05rem semibold, body 0.95rem, line height 1.5.
- **Layout:** one centred column, max about 760px wide, with generous spacing. Idea cards stack vertically. The technique label sits in the card's top-right corner as small uppercase muted text ("SCAMPER ← ANALOGIES").
- **Feedback panel:** expands inline under the card's buttons, with tag chips (toggle on tap), a one-line note field and a submit button. No modals.
- **Copy tone:** short, friendly and plain ("What are you trying to figure out?", "The agents are working…", "Save an idea in Explore to keep it here").
- **Avoid:** gradients, chat bubbles, dense tables, emoji-heavy UI.

## Components

### App Entry and Config
`__main__.py` parses `--demo` / `--reset-demo`, chooses the database, runs migrations-free `create_all()`, seeds the demo if needed, starts Uvicorn and opens the browser. `config.py` merges `config.toml` (reason tags, placeholder hints, active pattern, idea count, model, call timeout) with environment variables (`WHATELSE_MODE`, `WHATELSE_DATA_DIR`, `WHATELSE_PATTERN`, `WHATELSE_MODEL`).
PRD ref: `prd.md > Demo Mode`, `prd.md > States and Boundaries` (Privacy, Persistence).

### Web Routes and Pages
`web.py` holds the FastAPI routes. Full-page routes render `base.html`-derived pages. Action routes return HTML fragments for HTMX to swap in (the tab body, or one card). Every action route checks that the challenge is `active`, and otherwise returns the read-only view.

| Route | Purpose |
|---|---|
| `GET /` | welcome page (no challenges) or dashboard |
| `GET /challenges/new`, `POST /challenges` | new challenge form / create |
| `GET /challenges/{id}?tab=explore\|library\|experiments\|summary` | workspace |
| `POST /challenges/{id}/edit` | update statement/context (`context_edited` event) |
| `POST /challenges/{id}/generate` | run the collaborative pattern; returns new cards (pattern selector cut in build) |
| `POST /challenges/{id}/status` | pause / achieve / abandon / reopen (+ note) |
| `POST /challenges/{id}/delete` | permanent delete after confirmation (added in build): rows for the challenge in all four tables, plus matching agent-log lines |
| `GET /_version`, `POST /_shutdown` | code fingerprint; lets a newer launch stop a stale running copy (added in build) |
| `POST /challenges/{id}/ideas` | add the person's own idea (added in build): a `manual` run, an `Idea` with `techniques=["own"]`, status `saved` |
| `POST /ideas/{id}/save` · `/discard` · `/rework` · `/feedback` · `/action` · `/progress` · `/complete` | idea reactions |

PRD ref: `prd.md > Screens and Layout`, `prd.md > Challenges`, `prd.md > Reacting to Ideas (Explore)`, `prd.md > Idea Library`, `prd.md > Experiments`, `prd.md > Challenge Outcomes`.

### Templates and Styling
`templates/`: `base.html` (header, Demo badge, HTMX script), `welcome.html`, `dashboard.html`, `challenge_form.html`, `workspace.html` (header panel + tabs), and partials `_idea_card.html`, `_feedback_panel.html`, `_explore.html`, `_library.html`, `_experiments.html`, `_summary.html`, `_history.html`, `_error.html`. The challenge panel uses a native `<details>` element, so it's collapsed by default with no JavaScript. Generate uses `hx-indicator` for the working message and `hx-disabled-elt` to disable the button.
PRD ref: `prd.md > Screens and Layout`, `prd.md > Look and Feel`, `prd.md > States and Boundaries`.

### Idea and Challenge Service
`service.py` holds all state changes: create challenge, record a reaction, change an idea's status, change a challenge's status. Each function writes **one `Event` row and updates the current status in the same transaction**, so the status column and the event log can't disagree. It enforces the allowed transitions:
- Idea: `generated → saved | discarded | reworked`; `saved → actioned | discarded` (rework from the Library keeps it `saved`); `actioned → completed` (with verdict) `| discarded`.
- Challenge: `active → paused | achieved | abandoned`; any of those `→ active`.
PRD ref: `prd.md > Reacting to Ideas (Explore)`, `prd.md > Idea Library`, `prd.md > Experiments`, `prd.md > Challenge Outcomes`.

### Context Builder (learning boundary)
`context.py` exposes one function, `build_context(challenge_id) -> AgentContext`. `AgentContext` holds the statement, the context and a plain-text **history summary**, which has four sections:
- **Liked:** saved ideas, with tags and notes.
- **Rejected:** discarded ideas, with title, tags and note.
- **Reworked:** each original idea, the note, and the result.
- **Tried:** experiments with their progress, verdict and notes.

POC rule: include everything for this challenge, newest first, capped at about 40 items. Ideas still awaiting a reaction in Explore are listed by title only under "Already suggested, no reaction yet" (to avoid repeats), never as a preference. Nothing from other challenges is ever read.
PRD ref: `prd.md > Learning Loop`.

### Creative Agents and Orchestrator
- `techniques/*.md`: one file per technique (`reverse_thinking`, `random_associations`, `analogies`, `scamper`, `challenging_assumptions`). Each has a short frontmatter (`key`, `label`) and a body describing how that agent thinks. Editing a technique means editing its file.
- `patterns/collaborative.py` (**default**):
  - *(Revised in build, slice 1: three rounds and 10 ideas instead of two rounds and 5, because the first version's ideas weren't creative enough and 4 of 5 agents ignored the seeds.)*
  - **Round 1 (diverge):** 5 parallel calls. Each technique names the 3 most obvious moves (merged into a shared **banned list**) and returns 3 wild seeds (`title`, `text`), unfiltered for feasibility. The orchestrator gives every seed a stable id such as `analogies-1`.
  - **Round 2 (cross-pollinate):** 5 parallel calls. Each technique gets the context, the banned list and all *other* techniques' seeds, with their ids. It returns 2 ideas (`ideas_per_agent`), each of which must **fuse seeds from at least two other techniques** and avoid the banned list. Each lists `built_on` and `how`. The code checks the ids and records whether the fusion rule was met (`fused_two_techniques`), without rejecting ideas that miss it.
  - **Round 3 (push):** 5 parallel calls. Every draft is given to exactly one *other* agent (agent i pushes the first draft of agent i+1 and the second of agent i+2), which makes it bolder, replaces its most conventional part and makes it more specific. The pushed version replaces the draft, and the pushing technique is appended to `techniques`. A failed push keeps those drafts unchanged; a failed round-2 call fails the run.
  - **Attribution:** the orchestrator, not the model, works out `techniques` = the agent's own technique first, followed by the technique of every seed listed in `built_on` (no duplicates). It drops any seed id that doesn't exist. The card label reads e.g. "SCAMPER ← ANALOGIES + REVERSE THINKING". If `built_on` is empty, the label shows only the agent's own technique.
  - The round-1 seeds are stored in `GenerationRun.data` for later analysis, not shown.
- **Cut in build: the single-prompt baseline, the stage-1 blind comparison and the Pattern selector (Default / Collaborative / Single prompt / Blind).** You had already compared the collaborative pattern with a single prompt yourself and found the single prompt's ideas clearly weaker, so the formal comparison wasn't worth building. Patterns stay pluggable (`patterns/*.py`, `pattern` in `config.toml`), and every run still records its pattern, so a comparison can be added later.
- **Data kept for later analysis, with no analytics built now.** Every idea links to its run, and every run records the pattern and model. Every reaction is an event linked to the idea. So "pattern → idea → reaction" can be queried later, and nothing extra needs to be stored. There's no automatic pattern selection and no effectiveness dashboard.
- **Watching for convergence** (different agents producing variations of essentially the same idea), without building similarity detection:
  - Round-2 prompts tell each agent to aim for a direction the seeds *don't* already cover, not to polish the most obvious seed.
  - The discard tags include **"same as another idea"** (`duplicate`), so convergence is recorded as structured data whenever it's noticed.
  - All round-1 seeds and round-2 outputs, including `built_on`, are stored on the run. That makes it possible to check later whether several agents built on the same seed.
  - The stage-1 comparison notes include a convergence observation for each pattern.
- `orchestrator.py` loads the configured pattern by name, runs it, validates the output, and runs **Rework**. Rework is one call using the original idea's own technique(s), the user's note and tags, and the context, and it returns 1 idea.
- Prompt wording for patterns and Rework lives in `prompts/*.md`, not in Python strings.
- Parallel calls use `concurrent.futures.ThreadPoolExecutor` (5 workers).
- If a round-2 call fails, the whole run fails (no partial ideas; see `prd.md > States and Boundaries`).
- Adding another pattern means adding a file in `patterns/` and naming it in `config.toml` (or `WHATELSE_PATTERN`). Each run records which pattern produced it.
PRD ref: `prd.md > Generating Ideas`, `prd.md > Reacting to Ideas (Explore)` (Rework).

### LLM Adapter
`llm.py` is the only module that knows how agents are called. It exposes `complete(system: str, prompt: str, schema: dict) -> dict`. `ClaudeCLI` implements it, and `FakeLLM` returns canned ideas for tests (clearly labelled as a simulation, used only in tests). See `External Services and Dependencies > Claude Code CLI` for the exact call. Every call writes one JSON line (prompt, response, duration, tokens) to the private log folder.
PRD ref: `prd.md > Generating Ideas`, `prd.md > States and Boundaries` (generation fails).

### Closing Summary
`summary.py` computes, with plain queries: the outcome and note; counts of ideas generated, saved, discarded, reworked, actioned and completed; experiments with their verdicts; and saved ideas. It's rendered by `_summary.html`, shown on close, and available as the Summary tab on closed challenges.
PRD ref: `prd.md > Challenge Outcomes`.

### Demo Seed
*Cut in build (learner decision). `WHATELSE_MODE=demo` still selects `demo.db` and shows the badge; there is no seed file and no `--demo` / `--reset-demo` flags.*

`demo/seed.json` holds a fictional persona's challenge (statement + context) and, optionally, a few pre-made events so the Library isn't empty in screenshots. It's loaded into `demo.db` on first demo start. It contains no real data and is committed to the repo.
PRD ref: `prd.md > Demo Mode`.

## Data Model
Four tables (SQLModel). All timestamps are timezone-aware UTC. Tags are JSON lists of tag keys, never comma-separated strings. There's no raw SQL.

**`Challenge`**: `id`, `title` (first line of the statement, max 80 chars), `statement`, `context` (nullable), `status` (`active|paused|achieved|abandoned`), `outcome_note` (nullable), `created_at`, `updated_at`.

**`GenerationRun`**: `id`, `challenge_id`, `kind` (`generate|rework`), `pattern`, `model`, `status` (`running|succeeded|failed`), `error` (short text, nullable), `data` (JSON: round-1 seeds, etc.), `started_at`, `finished_at`.

**`Idea`**: `id`, `challenge_id`, `run_id`, `parent_idea_id` (nullable; set for reworks), `title`, `text`, `techniques` (JSON list of technique keys, own technique first), `built_on` (JSON list of round-1 seed ids, empty for single-prompt and rework ideas), `how` (nullable short text: how it used those seeds), `status` (`generated|saved|reworked|actioned|completed|discarded`), `verdict` (nullable: `worked|partly|didnt_work|dropped`), `created_at`, `updated_at`.

**`Event`** (append-only): `id`, `challenge_id`, `idea_id` (nullable), `type`, `tags` (JSON list), `note` (nullable), `from_status`, `to_status` (nullable), `data` (JSON, nullable), `created_at`.
Event types: `challenge_created`, `context_edited`, `challenge_status` (pause/achieve/abandon/reopen in `to_status`), `idea_created`, `saved`, `discarded`, `reworked`, `feedback`, `actioned`, `progress`, `completed`.

`GenerationRun.pattern` holds the pattern actually used, and `GenerationRun.data.requested` holds what was asked for (always `default` now that the selector is cut).

**Reason tags** live in `config.toml`. The discard list adds `duplicate` ("same as another idea") to the PRD's starting set, to record convergence. They're kept as `[tags.save]` and `[tags.discard]` lists of `{key, label}`. The database stores only keys, so labels can change without touching data.

### Where data lives
- **Data folder:** `WHATELSE_DATA_DIR` if set, otherwise the per-user app-data folder (`%LOCALAPPDATA%\WhatElse` on Windows, `~/.local/share/whatelse` elsewhere). It's outside the repo, so it can't be committed by accident.
- **Files:** `whatelse.db` (real), `demo.db` (demo), `logs/agent-calls.jsonl` (real mode) / `logs/demo-agent-calls.jsonl`.
- **Updates:** only through `service.py` (state changes) and the orchestrator (new ideas and runs).
- **Leaving and returning:** everything is in SQLite, so closing the browser or restarting the app loses nothing. A run left `running` by a crash is marked `failed` on startup, so Generate isn't blocked forever.

## File Structure

```
AI-Hackaton/
├── pyproject.toml            # project metadata, dependencies, [dev] extras, pytest config
├── README.md                 # what it is, setup, run, demo mode (written in 6-ship)
├── What Else.cmd             # double-click launcher (Windows): starts the app minimised, opens browser
├── .gitignore                # already ignores data/, *.db, logs/, private docs
├── src/whatelse/
│   ├── __main__.py           # `python -m whatelse`: flags, DB choice, seed, start server, open browser
│   ├── config.py             # loads config.toml + env vars
│   ├── config.toml           # reason tags, placeholder hints, pattern, idea count, model, timeout
│   ├── db.py                 # engine per mode, create_all, startup cleanup of stuck runs
│   ├── models.py             # Challenge, GenerationRun, Idea, Event (SQLModel)
│   ├── service.py            # all state changes: one event + status update per action
│   ├── context.py            # learning boundary: build_context(challenge_id)
│   ├── orchestrator.py       # runs a pattern, validates output, Rework
│   ├── llm.py                # ClaudeCLI adapter + FakeLLM for tests
│   ├── summary.py            # closing summary from stored data (no AI)
│   ├── web.py                # FastAPI app and routes
│   ├── techniques/           # one .md per creative technique (5 files)
│   ├── patterns/
│   │   └── collaborative.py  # default: diverge, cross-pollinate, push
│   ├── prompts/              # prompt text for rounds, history, rework
│   ├── templates/            # Jinja2 pages and HTMX partials (see Templates and Styling)
│   ├── static/
│   │   ├── style.css         # all styling (see Look and Feel)
│   │   └── htmx.min.js       # vendored HTMX 2.x
│   └── demo/seed.json        # fictional persona challenge (safe to commit)
├── tests/
│   ├── conftest.py           # temp DB + FakeLLM fixtures
│   ├── test_service.py       # transitions write events and statuses correctly
│   ├── test_context.py       # history summary content, challenge isolation
│   ├── test_orchestrator.py  # pattern output validated; failures leave no partial ideas
│   └── test_web.py           # key routes render; read-only when not active
├── scripts/                  # only if needed: one-off schema copy scripts (developer tools)
└── devpost/                  # planning docs (learner-profile.md and private/ are git-ignored)
```

Techniques, patterns, prompts, templates, static files, config and the seed live **inside the package** and are found relative to the package, not the working directory (`scope.md > Portability Considerations`).

## External Services and Dependencies

### Claude Code CLI
The only external dependency at runtime. It's verified on this machine (CLI 2.1.195, `claude.EXE` on PATH, subscription login, no API key).

**Exact call** (built by `llm.py` as an argument list; no shell):
```
claude -p "<prompt>"
  --output-format json
  --system-prompt "<technique/system text>"
  --json-schema '<JSON schema for the expected ideas>'
  --tools ""
  --strict-mcp-config
  --setting-sources ""
  --no-session-persistence
  [--model <model>]          # only if set in config; otherwise the CLI default
  [--effort <level>]         # from config (default "low"); added in build, see checklist Revisions
```
The prompt is sent on **stdin**, not as an argument, so long prompts don't hit the Windows command-line limit.
- **Response:** one JSON object. `is_error` is the success flag, and `structured_output` holds the parsed object matching the schema (also present as a string in `result`). `usage` and `duration_ms` go to the log.
- **Measured 2026-10-19:** these flags cut input from about 21k to **136 tokens** for a trivial call (783 for an idea prompt). A structured 2-seed call took about 10s, so a collaborative Generate is about 2 rounds × ~10–15s ≈ 20–30s.
- **Auth:** the claude.ai subscription login. `llm.py` refuses to run and shows an error if `ANTHROPIC_API_KEY` is set in the environment, to prevent accidental billing.
- **Limits/cost:** no per-call charge. Calls count against the subscription's usage limits (a collaborative Generate = 15 calls, Rework = 1).
- **Timeout:** 180s per call (configurable; raised from 120s in build). The subprocess is killed on timeout.
- **Do not use `--bare`:** it requires an API key and doesn't accept OAuth login.
- **Docs:** https://code.claude.com/docs/en/headless · https://code.claude.com/docs/en/cli-reference
- **Verify early in the build:** that `--json-schema` output stays reliable for arrays of 5 ideas, and how the CLI reports a usage-limit error (`is_error` + message), so the friendly message triggers correctly.

### Python packages
Listed in `Stack`. All installed and imported successfully on Python 3.14.2 on 2026-10-19.

## Important Failure Modes

- **Agent call fails** (CLI error, usage limit, timeout, invalid JSON) → the run is marked `failed`, no ideas are stored, and Explore shows "The agents couldn't finish. Try again in a moment." For Rework, the original idea is unchanged. Details go only to the private log. Implements `prd.md > States and Boundaries`.
- **Double Generate / stuck run** → the button is disabled while running. The server refuses a second run for the same challenge, and startup marks stale `running` runs as `failed`.
- **Claude not logged in / CLI missing / API key set** → a clear message on Generate explaining which of the three it is. The rest of the app (browsing, reactions) keeps working.

## What Was Simplified and Why

- **Synchronous Generate request** instead of a background job with progress polling. A 20–40s request with an HTMX loading indicator is fine locally. The fuller version would need a job queue and a status endpoint.
- **`create_all()` with no Alembic.** The schema is kept stable, and any rare change is handled with a one-off copy script in `scripts/`. Alembic gets added before anyone else uses the app (`scope.md > Portability Considerations`).
- **Reason tags in config** instead of a database table. The tags are a fixed list, and storing keys keeps the data analysis-ready.
- **Context builder includes everything up to a cap** instead of relevance ranking. That's enough for one challenge's history, and the boundary is ready for a smarter version.
- **No live grounding/web research.** The ideas are pure ideation (`prd.md > Deferred From the POC`).
- **Fake LLM only in tests.** The app itself always uses the real agents, because the kernel is never simulated.

## Decisions and Open Issues

**Learner decisions**
- **Python 3.14 + venv/pip instead of uv + 3.12**, provided the dependencies are compatible. The agent verified compatibility on 2026-10-19.
- **Stack from `scope.md > Technical Direction`:** FastAPI, SQLModel/SQLite, Jinja2 + HTMX, a `claude -p` adapter, and techniques/patterns as files.
- **Local only, no deployment.** The submission is a demo video plus the public repository.

- **Revised in build:** the collaborative pattern became three rounds (diverge with a banned list of obvious moves, cross-pollinate with a two-technique fusion rule, push) producing 10 ideas from 15 calls, about 2 minutes at low effort. Your decision after judging the first version "not super creative".
- **The collaborative two-round pattern** (5 seed calls, then 5 build-on calls, all in parallel; 10 calls per Generate) was the starting default. **Round 2 is open:** each agent may extend, invert, challenge or recombine any number of other agents' seeds, whichever produces the strongest unconventional idea. Technique attribution is preserved for every seed used. The agent recommended the two rounds; you confirmed them and removed the two-technique restriction. Tradeoff accepted: more subscription usage per Generate.
- **Revised in build: single-prompt baseline and comparison cut** (you had already compared informally; collaborative was clearly better). Original decision: **Keep the single-prompt baseline, and run the comparison as a genuine experiment.** The aim is to discover whether multi-agent collaboration produces better ideas, not to prove that it does. The first blind comparison sets a **provisional** default only. Both patterns stay selectable (including a Blind option) for further testing, because different approaches may suit different challenges or stages.
- **Preserve data, don't analyse it yet.** The pattern is recorded per run, so every idea and reaction can be traced back to it. Convergence is watched for through a `duplicate` discard tag and the stored seeds/`built_on`. There's no automatic pattern selection or analytics in the MVP.

**Implementation details derived by the agent**
- Data folder location, event types, the status transition rules, the 40-item history cap, the 120s timeout, the API-key guard, and treating unreacted ideas as "already suggested" (for de-duplication only, never as a preference).

**The useful unknown: running multi-agent work on a subscription without paid API calls** (from `learner-profile.md > Desired Learning Outcome`).
- **What clarified it:** a live test showed that `claude -p` with a custom system prompt, no tools, no MCP servers and no setting sources costs about 136 input tokens instead of about 21k. That turned "fewer, richer calls" from a necessity into a choice. `--json-schema` gives validated structured output.
- **Still to check in build stage 1:** how fast real usage limits are reached with 15 calls per Generate (the collaborative-vs-single-prompt question was settled informally by you, see above).

**Open issues**
- **Collaborative vs single-prompt quality:** settled informally by you during the build: collaborative was clearly better.
- **How lineage is shown on reworked cards:** a "Reworked from: <title>" line is the default and can be refined during the build (`prd.md > Open Questions`).
- **Usage-limit error format:** verify early in the build (see `External Services and Dependencies > Claude Code CLI`).
