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

- [x] **4. The agents learn from your reactions, and Rework reshapes an idea**
  Becomes usable: Generate now sees this challenge's history (liked, rejected, reworked, tried, plus titles already suggested). Rework (a required note plus optional tags) returns one new idea, labelled "Reworked from: …", into Explore. The statement and context can be edited from the header panel.
  Why now: This is build stage 2, the learning half of the kernel. It needs reactions from slice 3 to exist. Moved ahead of the pattern comparison at the learner's request.
  PRD ref: `prd.md > Learning Loop`, `prd.md > Reacting to Ideas (Explore)` (Rework), `prd.md > Challenges` (editing)
  Spec ref: `spec.md > Components > Context Builder (learning boundary)`, `spec.md > Components > Creative Agents and Orchestrator` (Rework)
  Build: `context.py` `build_context` (capped at about 40 items, newest first, scoped to one challenge) wired into both patterns. `/ideas/{id}/rework` with lineage (`parent_idea_id`; the original becomes `reworked` in Explore and stays `saved` in the Library). `POST /challenges/{id}/edit` with a `context_edited` event. `tests/test_context.py`.
  Verify (mechanical): `pytest` (the summary contains each section; unreacted ideas appear only as titles; challenge A's history never shows up in challenge B; a failed rework leaves the original untouched). One real Rework and one real Generate after a discard tagged "already tried".
  Learner check: Discard an idea as "already tried", rework another with a note, then Generate again. Is the rework reshaped around your note, and do the new ideas avoid the rejected one?
  Commit: `Add learning context and Rework`

- [x] **5. Develop saved ideas: Library actions and Experiments**
  Becomes usable: In the Library you can Move to Action, Add feedback, Rework or Discard an idea, and expand its history. The Experiments tab lets you log dated progress and finish with a verdict (Worked / Partly / Didn't work / Dropped).
  Why now: This is build stage 3. Experiment outcomes are the strongest learning signal, and `context.py` already reads them.
  PRD ref: `prd.md > Idea Library`, `prd.md > Experiments`
  Spec ref: `spec.md > Components > Idea and Challenge Service`, `spec.md > Components > Templates and Styling` (`_library`, `_experiments`, `_history`)
  Build: `/feedback`, `/action`, `/progress`, `/complete` routes and transitions. The history partial. Status badges. Running experiments shown first, then finished ones.
  Verify (mechanical): `pytest` (transitions for actioned, completed and discarded-from-Library; feedback leaves the status unchanged; progress entries come out oldest first; the verdict is stored and appears in the context).
  Learner check: Move a saved idea to Action, log two progress notes, finish it as "Worked", and expand its history.
  Commit: `Add Idea Library actions and Experiments`

- [x] **6. Several challenges: dashboard, close / pause / reopen, closing summary**
  Becomes usable: The dashboard lists challenges (Active, then Paused, then closed) with status and last activity. Challenges can be closed as Achieved or Abandoned, paused, and reopened. A non-active challenge is read-only. A closing summary appears on close and as a Summary tab.
  Why now: This is build stage 4. The data was keyed to challenges from slice 2, so this is UI and service work only.
  PRD ref: `prd.md > Screens and Layout` (Dashboard), `prd.md > Challenge Outcomes`
  Spec ref: `spec.md > Components > Web Routes and Pages` (status route, read-only), `spec.md > Components > Closing Summary`
  Build: `dashboard.html`, `/challenges/{id}/status`, read-only guards on every action route, `summary.py` + `_summary.html`, `tests/test_web.py`.
  Verify (mechanical): `pytest` (summary counts are correct; a closed challenge refuses Generate and reactions; reopening restores them; every status change writes an event; dashboard order is correct).
  Learner check: Create a second challenge, switch between the two, close one as Achieved and read its summary, then reopen it.
  Commit: `Add dashboard, challenge outcomes and closing summary`

## Hands-on Checkpoints

- [x] Early usable behavior explored — after slice 1 (judged the raw agent ideas; led to the three-round, 10-idea pattern) and again after slice 4 (learning loop confirmed good)
- [x] Final kick-the-tires exploration and feedback completed — learner tried each slice in the running app (real challenge, real agents); last pass covered the challenge lifecycle and delete

## Final Review

- [x] Final review complete — feedback resolved and learner confirms ready to ship

Findings and outcome: feedback during the build was folded in as it came (three-round 10-idea pattern, "too much work" tag, learning loop moved earlier, own ideas, delete challenge, stale-copy launcher fix, single-prompt comparison and demo mode cut). At the end the learner said "As an MVP this is great. I will use it and rework as needed in real use" — no further revisions requested. Verified: `pytest` 54 passed; app started via `What Else.cmd` on the latest code and `/` returned 200.

## Code Tour and App Map

- [x] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [x] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [x] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: Prior practice connected, not repeated. In slice 1 the learner judged the agent output and the build measured it: only 1/5 agents built on seeds, and replaying one logged call showed thinking effort drove latency (low ~20s / medium ~106s / default ~123s). The redesigned three-round pattern was then measured at 10/10 drafts fusing two or more techniques (Revisions; `fused_two_techniques` in `patterns/collaborative.py`; summary line in `try.py`). This ties to the desired outcome: multi-agent collaboration on a subscription.
Route and stops: Reference-only route in the map (not toured): `web.py` `generate` → `orchestrator.py` `run_generate` → `patterns/collaborative.py` `run` (round1/round2/round3, `_assign_pushes`).
Edit outcome: Not applicable (no extra exercise; the learner made product changes throughout the build).
Reflection: Transfer question offered at hand-off.
Activity mode: Prior practice plus brief recap; app map generated from commit ebfa097 and checked against source (all paths and symbols verified).

## Revisions

- Brought demo mode back at submission (2026-10-25) as a hosted sample — the submission checklist needs a public site judges can use without an account, and live agents need the user's own Claude Code login. `demo.py` replays agent answers recorded from real runs (`tools/record_demo.py`: 3 Generates, 27 reworks) through the normal pattern code; the fictional bookshop sample is rebuilt on every start and by **Reset demo**; new challenges and `/_shutdown` are refused; a sample-mode intro says what the app does and who it's for, and the full challenge and context are shown. Hosted on Render's free plan (`render.yaml`) at https://what-else-demo.onrender.com. Verified: `pytest` 61 passed; a Playwright walkthrough (Generate, Save, Discard, Rework, Library, Experiments, close → Summary, Reset, 400px width) passed locally and on the hosted site. Updated `spec.md`, `prd.md` and `scope.md`.
- Prompts go to `claude -p` on stdin instead of as an argument — long prompts (history, pasted CVs) would hit the Windows command-line length limit; stdin was tested and works.
- Added an `effort` setting (`--effort`, default `low`; `WHATELSE_EFFORT` / `--effort` overrides) and raised the per-call timeout to 180s — real calls on the CLI default model ran far slower than the 10s measured in planning (round 2: 56–120s, one 120s timeout). Replaying one round-2 call: low ~20s, medium ~106s, default ~123s. A full collaborative Generate at low effort took 82s.
- Collaborative pattern rebuilt as three rounds producing 10 ideas (diverge with a shared banned list of obvious moves → cross-pollinate, 2 ideas per agent each fusing seeds from two or more other techniques → push, where another agent makes each draft bolder and more specific), and `idea_count` = 10 for the single-prompt baseline — the learner judged the two-round, 5-idea output "not super creative", and only 1 of 5 agents had built on others' seeds. Sample run: 10/10 drafts fused two or more techniques, all 10 pushed, 125s, 15 calls. Updated `prd.md` (about 10 ideas) and `spec.md > Creative Agents and Orchestrator`.
- Cut demo mode (was slice 7: seeded fictional persona, `--demo`/`--reset-demo`) — learner decision; the launcher half of that slice was already built in slice 4. The existing `WHATELSE_MODE=demo` setting still selects a separate, empty `demo.db` with a "Demo" badge, and `WHATELSE_DATA_DIR` can point at any separate folder.
- Added "Delete challenge" to slice 6 — learner request, reversing the PRD non-goal for whole challenges (ideas still can't be deleted). Confirmation prompt; removes all rows for the challenge and purges agent-log lines whose prompt contains any of its statements; refused while a run is in progress.
- The launcher now replaces a stale running copy: the server exposes a code fingerprint (`/_version`) and a token-protected `/_shutdown`, and `python -m whatelse` stops an out-of-date copy before starting — after an update, the old process kept serving new templates with old code and threw an Internal Server Error.
- Added "Add your own idea" to slice 5 (Library form → saved idea labelled YOUR IDEA, visible to the agents as the person's own) — learner request, so all ideas, theirs and the agents', live in one place. No schema change: each own idea gets a `manual` GenerationRun and `techniques=["own"]`. Assumption: own ideas start in the Library, not Explore.
- Cut the single-prompt baseline / blind comparison slice (was slice 5; later slices renumbered 5–7) — the learner had already compared the collaborative agents with a single prompt informally and judged the single prompt clearly worse, so the formal experiment adds nothing. Patterns stay pluggable.
- `What Else.cmd`, the already-running check and a desktop shortcut were pulled forward from slice 8 into slice 4 — the learner asked for a desktop shortcut for daily use; slice 8 now only needs demo mode.
- Rework takes a required note only, no reason tags (assumption) — the note is the instruction, and neither tag list fits "change this"; it can be added if it's missed. A rework is refused while a Generate is running on the same challenge.
- Learning loop + Rework (now slice 4) moved ahead of the pattern comparison (now slice 5) — the learner wanted the agents learning from reactions sooner; the comparison stays fair because both patterns receive the same history.
- Slice 2 includes a bare challenge list at `/` once a challenge exists (slice 7 adds ordering, last activity and outcomes) and all three tabs with their empty states — the home page needed somewhere to go after the first challenge, and the tabs cost nothing to show early.
- Round 1 tolerates a single failed agent (its seeds are just missing); round 2 stays all-or-nothing as specified — one flaky call out of five shouldn't throw away a 10-call run before any idea exists.
- Usage-limit error format still unverified (no way to trigger it on demand); `is_error` + message is classified, with a login-message heuristic for "not logged in".

