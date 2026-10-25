---
doc: checklist
status: approved
---

# Build Checklist

Build mode: learn

## Slices

- [x] **1. The five agents collaborate on a challenge and return ideas (terminal)**
  Becomes usable: A command, `python -m whatelse.try "<challenge>"`, runs the collaborative pattern for real through `claude -p` and prints about 10 ideas, each with its technique label, `built_on` and `how`.
  Why now: The agents are the kernel and the biggest unknown: whether `--json-schema` is reliable, how fast two parallel rounds run, how a usage-limit error looks, and whether the ideas are any good. This is the one allowed "layer first" slice, because it proves the critical risk and leaves runnable evidence. It also includes the project scaffold.
  PRD ref: `prd.md > Generating Ideas`
  Spec ref: `spec.md > Stack`, `spec.md > File Structure`, `spec.md > Components > Creative Agents and Orchestrator`, `spec.md > Components > LLM Adapter`, `spec.md > External Services and Dependencies > Claude Code CLI`
  Build: `pyproject.toml`, venv install, package skeleton under `src/whatelse/`, `config.py` + `config.toml`, `llm.py` (`ClaudeCLI` with API-key guard, timeout, JSONL log to the private data folder; `FakeLLM`), five `techniques/*.md`, `prompts/*.md` for both rounds, `patterns/collaborative.py` (attribution worked out in code), `orchestrator.py` (validate with Pydantic), a small `try` entry point, `tests/test_orchestrator.py` using FakeLLM.
  Verify (mechanical): `pytest` passes (attribution, bad seed ids dropped, a failed round-2 call fails the run). One real run of `python -m whatelse.try` returns 5 validated ideas. Record the timing, and record how an error is reported (`is_error`), in Revisions.
  Learner check: Run `python -m whatelse.try` with a challenge of your own and read the ideas. Do they feel unconventional? Do the technique labels and the "how it built on others" lines make sense?
  Commit: `Add collaborative creative agents with Claude CLI adapter`

- [x] **2. Start a challenge in the browser and generate ideas into Explore**
  Becomes usable: `python -m whatelse` opens the app. The welcome screen leads to the new-challenge form, and that leads to the workspace. Generate shows "The agents are working…" and then idea cards appear in Explore. Everything is stored in SQLite and survives a restart.
  Why now: This puts the kernel behind the real interface as soon as it's proven, and sets up the data model every later slice writes to.
  PRD ref: `prd.md > The Core Journey` (steps 1–3), `prd.md > Challenges`, `prd.md > Generating Ideas`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > The Core Journey Through the System`, `spec.md > Components > App Entry and Config`, `spec.md > Components > Web Routes and Pages`, `spec.md > Components > Templates and Styling`, `spec.md > Data Model`, `spec.md > Look and Feel`, `spec.md > Important Failure Modes`
  Build: `models.py` (all four tables), `db.py` (data folder, `create_all`, mark stuck runs failed on startup), `service.py` (create challenge plus events), `web.py` with `/`, `/challenges/new`, `POST /challenges`, the workspace, and `POST /generate` (refuses a second run while one is running; on a failed run, shows the friendly message and stores no ideas). Templates `base`, `welcome`, `challenge_form`, `workspace`, `_explore`, `_idea_card`, `_error`. `style.css`, vendored `htmx.min.js`, and `__main__.py` (start server, open browser).
  Verify (mechanical): `pytest` with TestClient and FakeLLM (welcome shows when the DB is empty; empty statement blocked; generate stores ideas with `idea_created` events; a failed run stores none; a second run while one is running is refused). Start the server, then curl `/` and the workspace. One real Generate through the server.
  Learner check: Run `python -m whatelse`, start a challenge, click Generate, and wait for the cards. Restart the app and confirm the cards are still there.
  Commit: `Add challenge creation, workspace and Generate`

- [x] **3. Save and discard ideas with one-tap reasons**
  Becomes usable: Each card has Save, which opens a panel with save tags and a note, and Discard, which does the same with discard tags. A saved idea leaves Explore and appears in a simple Idea Library tab. A discarded idea disappears but is kept. Tab counts are shown.
  Why now: Reactions are the raw material for the learning loop and complete build stage 1. Every reaction is written to the event log from the start.
  PRD ref: `prd.md > Reacting to Ideas (Explore)`, `prd.md > Look and Feel`
  Spec ref: `spec.md > Components > Idea and Challenge Service`, `spec.md > Components > Templates and Styling`, `spec.md > Data Model` (Reason tags)
  Build: Service transitions with events (`saved`, `discarded`) and allowed-transition checks. `/ideas/{id}/save` and `/discard`. `_feedback_panel.html` with tag chips from config. The Library tab list. `tests/test_service.py`.
  Verify (mechanical): `pytest`: the status and the event always change together; tags are stored as key lists; disallowed transitions are refused; unreacted ideas stay in Explore after another Generate. In the browser, Save with no note takes two taps.
  Learner check: Save one idea with a reason, discard another, and check the Library tab. Does picking reasons feel quick enough that you'd actually do it?
  Commit: `Add save and discard reactions with reason tags`

- [ ] **4. Pick the pattern: single-prompt baseline and blind comparison**
  Becomes usable: A Pattern selector next to Generate offers Default, Collaborative, Single prompt and Blind. Cards never show which pattern made them. "Show how these were made" reveals it after you've judged.
  Why now: This settles the core assumption in build stage 1 (does multi-agent collaboration beat one rich prompt?) before more is built on the collaborative pattern. The result sets the provisional default in `config.toml`.
  PRD ref: `prd.md > What We're Building` (stage 1 comparison), `prd.md > Open Questions`
  Spec ref: `spec.md > Components > Creative Agents and Orchestrator` (single prompt, comparison, Blind, convergence)
  Build: `patterns/single_prompt.py` + prompt, given equal care. The selector, with `requested` vs actual pattern stored on the run. The run summary reveal.
  Verify (mechanical): `pytest` (each option records the right pattern; blind records `requested=blind` and a real pattern; no pattern name appears in the card HTML). One real single-prompt run.
  Learner check: Run the stage-1 comparison on the same challenge using Blind a few times. Judge the cards by gut, then reveal. Which pattern should be the provisional default?
  Commit: `Add single-prompt baseline and blind pattern selection`

- [ ] **5. The agents learn from your reactions, and Rework reshapes an idea**
  Becomes usable: Generate now sees this challenge's history (liked, rejected, reworked, tried, plus titles already suggested). Rework (a required note plus optional tags) returns one new idea, labelled "Reworked from: …", into Explore. The statement and context can be edited from the header panel.
  Why now: This is build stage 2, the learning half of the kernel. It needs reactions from slice 3 to exist.
  PRD ref: `prd.md > Learning Loop`, `prd.md > Reacting to Ideas (Explore)` (Rework), `prd.md > Challenges` (editing)
  Spec ref: `spec.md > Components > Context Builder (learning boundary)`, `spec.md > Components > Creative Agents and Orchestrator` (Rework)
  Build: `context.py` `build_context` (capped at about 40 items, newest first, scoped to one challenge) wired into both patterns. `/ideas/{id}/rework` with lineage (`parent_idea_id`; the original becomes `reworked` in Explore and stays `saved` in the Library). `POST /challenges/{id}/edit` with a `context_edited` event. `tests/test_context.py`.
  Verify (mechanical): `pytest` (the summary contains each section; unreacted ideas appear only as titles; challenge A's history never shows up in challenge B; a failed rework leaves the original untouched). One real Rework and one real Generate after a discard tagged "already tried".
  Learner check: Discard an idea as "already tried", rework another with a note, then Generate again. Is the rework reshaped around your note, and do the new ideas avoid the rejected one?
  Commit: `Add learning context and Rework`

- [ ] **6. Develop saved ideas: Library actions and Experiments**
  Becomes usable: In the Library you can Move to Action, Add feedback, Rework or Discard an idea, and expand its history. The Experiments tab lets you log dated progress and finish with a verdict (Worked / Partly / Didn't work / Dropped).
  Why now: This is build stage 3. Experiment outcomes are the strongest learning signal, and `context.py` already reads them.
  PRD ref: `prd.md > Idea Library`, `prd.md > Experiments`
  Spec ref: `spec.md > Components > Idea and Challenge Service`, `spec.md > Components > Templates and Styling` (`_library`, `_experiments`, `_history`)
  Build: `/feedback`, `/action`, `/progress`, `/complete` routes and transitions. The history partial. Status badges. Running experiments shown first, then finished ones.
  Verify (mechanical): `pytest` (transitions for actioned, completed and discarded-from-Library; feedback leaves the status unchanged; progress entries come out oldest first; the verdict is stored and appears in the context).
  Learner check: Move a saved idea to Action, log two progress notes, finish it as "Worked", and expand its history.
  Commit: `Add Idea Library actions and Experiments`

- [ ] **7. Several challenges: dashboard, close / pause / reopen, closing summary**
  Becomes usable: The dashboard lists challenges (Active, then Paused, then closed) with status and last activity. Challenges can be closed as Achieved or Abandoned, paused, and reopened. A non-active challenge is read-only. A closing summary appears on close and as a Summary tab.
  Why now: This is build stage 4. The data was keyed to challenges from slice 2, so this is UI and service work only.
  PRD ref: `prd.md > Screens and Layout` (Dashboard), `prd.md > Challenge Outcomes`
  Spec ref: `spec.md > Components > Web Routes and Pages` (status route, read-only), `spec.md > Components > Closing Summary`
  Build: `dashboard.html`, `/challenges/{id}/status`, read-only guards on every action route, `summary.py` + `_summary.html`, `tests/test_web.py`.
  Verify (mechanical): `pytest` (summary counts are correct; a closed challenge refuses Generate and reactions; reopening restores them; every status change writes an event; dashboard order is correct).
  Learner check: Create a second challenge, switch between the two, close one as Achieved and read its summary, then reopen it.
  Commit: `Add dashboard, challenge outcomes and closing summary`

- [ ] **8. Demo mode and the double-click launcher**
  Becomes usable: `python -m whatelse --demo` opens a separate `demo.db` seeded with a fictional persona, with a "Demo" badge. `--reset-demo` re-seeds it. Double-clicking `What Else.cmd` starts the app minimised, or just opens the browser if the app is already running.
  Why now: This is build stage 5. It's needed for the demo video in `6-ship`, and it's safest last, once the real flow is stable.
  PRD ref: `prd.md > Demo Mode`
  Spec ref: `spec.md > Components > Demo Seed`, `spec.md > Where It Runs and How Someone Tries It`
  Build: `demo/seed.json` (fictional and neutral), mode handling in `__main__.py`/`config.py`/`db.py`, the badge, separate demo logs, `What Else.cmd`, and the check for an already-running app.
  Verify (mechanical): `pytest` (demo and real modes use different DB files; seeding happens once; reset touches only `demo.db`). Start both modes and confirm each shows only its own challenges.
  Learner check: Start demo mode and run through the one-minute demo flow from `scope.md > What "Working" Looks Like`. Then double-click `What Else.cmd` and confirm your real challenges open.
  Commit: `Add demo mode and Windows launcher`

## Hands-on Checkpoints

- [ ] Early usable behavior explored — after slice 1 (judge the raw agent ideas), and after slice 4 (blind comparison sets the provisional default pattern)
- [ ] Final kick-the-tires exploration and feedback completed

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence:
Route and stops:
Edit outcome:
Reflection:
Activity mode:

## Revisions

- Prompts go to `claude -p` on stdin instead of as an argument — long prompts (history, pasted CVs) would hit the Windows command-line length limit; stdin was tested and works.
- Added an `effort` setting (`--effort`, default `low`; `WHATELSE_EFFORT` / `--effort` overrides) and raised the per-call timeout to 180s — real calls on the CLI default model ran far slower than the 10s measured in planning (round 2: 56–120s, one 120s timeout). Replaying one round-2 call: low ~20s, medium ~106s, default ~123s. A full collaborative Generate at low effort took 82s.
- Collaborative pattern rebuilt as three rounds producing 10 ideas (diverge with a shared banned list of obvious moves → cross-pollinate, 2 ideas per agent each fusing seeds from two or more other techniques → push, where another agent makes each draft bolder and more specific), and `idea_count` = 10 for the single-prompt baseline — the learner judged the two-round, 5-idea output "not super creative", and only 1 of 5 agents had built on others' seeds. Sample run: 10/10 drafts fused two or more techniques, all 10 pushed, 125s, 15 calls. Updated `prd.md` (about 10 ideas) and `spec.md > Creative Agents and Orchestrator`.
- Slice 2 includes a bare challenge list at `/` once a challenge exists (slice 7 adds ordering, last activity and outcomes) and all three tabs with their empty states — the home page needed somewhere to go after the first challenge, and the tabs cost nothing to show early.
- Round 1 tolerates a single failed agent (its seeds are just missing); round 2 stays all-or-nothing as specified — one flaky call out of five shouldn't throw away a 10-call run before any idea exists.
- Usage-limit error format still unverified (no way to trigger it on demand); `is_error` + message is classified, with a login-message heuristic for "not logged in".

