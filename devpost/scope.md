---
doc: scope
status: approved
revised: 2026-10-19 (challenge-first onboarding replaces the permanent profile; multiple challenges; staged build order; Rework merges Tweak and Explore further; generic reason tags; export dropped; portability considerations recorded)
---

# What Else?

A local creative studio where AI agents, each using a different creative-thinking technique, generate unconventional possibilities for a challenge you describe, and learn from your feedback until the challenge is resolved.

**Public framing:** *What Else?* is a collaborative creative-thinking engine for any challenge where the obvious answers aren't enough.

## The Unique Kernel
Collaborating creative agents (reverse thinking, random associations, analogies, SCAMPER, challenging assumptions) generate possibilities that the user would never think to ask for. The possibilities are not predefined: "this is the whole idea of the app: to create possibilities, not for me to define it beforehand."

Every reaction counts. Saved, discarded, reworked and actioned ideas, with their feedback and outcomes, all feed the next creative session, so the system gets more useful and stops repeating itself.

## Built to Finish, Not to Keep You
People use What Else? for a short, focused stretch: until they find an idea that works. They may never need it again, or they may come back months later with a different problem. So:
- **Fast start:** describe the problem and generate ideas straight away. Background context is optional, never a prerequisite.
- **Organised around a challenge, not a person:** ideas, feedback and experiments belong to a challenge, such as "Find my next role" or "Launch a new product". Someone can work on several challenges at once.
- **Clear outcomes:** a challenge ends as Achieved or Abandoned, or is set aside as Paused. Closing one feels like success, not churn.
- **Nothing is lost:** closed challenges stay in the app with their ideas, feedback and experiment history, ready to revisit or reopen.

## Who It's For
Anyone who wants fresh, creative ideas for a challenge and is tired of the obvious answers. For example: a small business looking for new ways to bring customers in, someone planning their next career move, a team naming or launching a product, an organiser trying to get people to turn up, or someone stuck on a personal project. Today they brainstorm alone or ask a single chatbot, and both tend to produce the same conventional ideas.

**Built for genuine use, not just a demo.** A concrete real-world use case guides the design. Its details are in a private, git-ignored document (`devpost/private/use-case.md`) that the planning skills read alongside this scope. That document holds only what can't be public; everything else lives here.

## The Core Loop
1. **Start a challenge:** write a few sentences about the problem ("What are you trying to figure out?"). Optionally add context. Placeholder hints in the context box nudge towards what makes ideas personal, without adding steps: "What do you bring that isn't obvious at first glance? What have you already tried? Any constraints?" Pasting in a CV or notes works too. You can add or edit this context at any point. Start another challenge whenever you like and switch between them; each keeps its own ideas, feedback and history.
2. Click **Generate**. About 5 ideas appear, each labelled with the technique that produced it.
3. React to each one:
   - **Save**: say what you like about it (quick reasons plus an optional note). It goes to the Idea Library. Knowing what you like matters as much as knowing what you don't.
   - **Discard**: say why, with quick reasons plus an optional note. It is stored, never deleted.
   - **Rework**: send the idea and your feedback back to the agents to develop, adjust or rethink it.
4. In the **Idea Library**, for each saved idea:
   - **Move to Action**: it enters an Actioned/Experiments area where you record what you're doing, your progress and the eventual results.
   - **Add feedback**: add new thoughts without changing the idea's status.
   - **Rework**: the same action as on new ideas, sending the idea and your feedback back to the agents.
   - **Discard**: explain why you've changed your mind.
5. The next Generate draws on all of it: the challenge, any context, likes and rejections with reasons, reworks, comments and outcomes. That history *informs* creativity without fencing it in. A rejected idea may still contain a useful element worth recombining.
6. **Close or pause the challenge:** close it as Achieved or Abandoned, optionally with a short note on what worked or why you stopped, or pause it to set it aside for now. A closing summary shows what you tried and what came of it (plain counts and lists built from the stored data, with no AI call).

**Idea lifecycle:** Generated → Saved → Actioned → Completed, with Discard possible at any stage before Completed. Discarding never erases anything. It only moves the idea out of the active collection. Each idea keeps its complete history: the original text, the feedback given when it was saved, later comments, and every status change.

**Challenge lifecycle:** Active → Achieved / Abandoned / Paused. Nothing is final: a challenge in any of these states can return to Active with all its history (e.g. the idea that worked turns out not to last, or an abandoned direction looks worth another go). Every status change, including reopening, is recorded as an event. Nothing is ever deleted. What happens to Saved or Actioned ideas while their challenge is closed is for `3-prd` to settle (most likely they stay as they are, frozen with the challenge).

## Inspiration & Identity
No reference product: "I haven't seen anything like it." The idea-card design in the original mockup is clean, light and card-based, with the technique label shown in the corner of each card, a dark Save button, an outlined Discard button, and an inline feedback panel ("Why isn't this idea right for you?" with quick reasons, an optional note, and Submit feedback). The UX should be simple and friendly. The interaction details still need more thought, which `3-prd` covers.

## Why This Matters
Conventional brainstorming, and a single AI prompt, keep producing the same predictable ideas. This project tests whether creative agents that each think differently, and build on each other's work, can surface more original and still practical possibilities, and get better as they learn what you liked and what worked. The user's test for an idea is gut, not a score: if it's interesting, practical and achievable in the time available, try it and see what happens.

## What "Working" Looks Like
Demo in about a minute, recorded with a **fictional persona** on a **completely separate demo database**, never real user data:
1. Type a one-paragraph challenge. No profile set-up is needed.
2. Click **Generate**. About 5 technique-labelled ideas appear.
3. Save one, discard one with a reason, and rework one.
4. **The "oh, that's cool" beat:** the reworked idea comes back reshaped around the feedback, and the saved idea sits in the Library, where it can be marked Actioned with an outcome.
5. Generate again. The new ideas visibly respond to the feedback: no straight repeats of rejected ideas, and where useful, a fresh idea that recombines an element of a rejected one in a new direction.
6. Mark the challenge Achieved and see its closing summary.

## The POC Boundary
The full loop, across **multiple challenges**, with every part kept thin except the agents:
- **Challenge:** a short problem statement plus optional free-text context with placeholder hints, both editable at any time. No guided questionnaire, no AI-organised profile, and no profile suggestions.
- **Multiple challenges:** a simple challenge list showing each challenge's status; start a new challenge at any time and switch between them. Everything (ideas, events, generation runs, learning context) is scoped to one challenge, and nothing carries over between challenges.
- **Creative agents:** one definition per technique (5 techniques) and one collaboration pattern where agents genuinely build on each other's ideas (e.g. a shared round where each agent takes others' ideas and extends, inverts or recombines them using its own technique), not independent generation followed by a selector. Techniques and collaboration patterns are easy to modify and experiment with, so changing them means editing a definition, not rewriting the app.
- **Idea repository:** every generated idea is saved automatically with its technique, status and full history (feedback, comments, status changes).
- **Reactions on new ideas:** Save with reasons / Discard with reasons / Rework.
- **Idea Library:** Move to Action, Add feedback, Rework, Discard. Actioned ideas track what you're doing, progress and results through to Completed.
- **Learning loop:** the challenge, its context and a history summary go into every generation, so the agents avoid straight repeats and build on outcomes, while staying free to mine rejected ideas for useful parts.
- **Challenge outcome:** close as Achieved or Abandoned with an optional note, or pause; return a challenge in any of these states to Active; see a simple closing summary generated by ordinary code, not an agent call.
- **Structured, analysis-ready data:** challenges, ideas, techniques (and technique combinations), feedback, save/discard reasons, status history and outcomes are stored as structured records with consistent tags, not just free text, so ordinary code can query them later.
- **Learning logic kept separate from the creative agents:** a distinct context/learning component decides what history the agents receive. In the proof of concept it can be simple (e.g. recent and relevant feedback), but it sits behind its own boundary so a Python analysis layer can replace it later without reworking the agents.
- **Domain-agnostic core:** the creative engine, agent collaboration, idea repository, feedback and learning loop contain no logic for any particular domain. Reason tags (e.g. "too vague", "not practical", "not me", "already tried", "too slow") and placeholder hints are generic, so any challenge works. The challenge statement carries the framing, and any remaining wording lives in config files, not code.
- **Privacy by default:** the user's real challenges, ideas, feedback and outcomes stay private. The real database, agent call logs and any prompt/response dumps live only in git-ignored local paths. The repository, logs, screenshots, demo video and submission contain no personal information.
- **Real use first:** the default mode runs on the user's own private database, and data persists across sessions and restarts. Every feature in the loop must work for genuine day-to-day use, not just look right in the demo.
- **Demo mode:** a fictional persona's challenge plus a separate demo database (e.g. chosen by a config setting or environment variable). It's used for the video and screenshots and is safe to commit as seed data.
- **Simple local web UI** with SQLite.
- **No paid API calls:** agents run on an existing Claude subscription through Claude Code headless mode (`claude -p`). **Verified 2026-10-18:** with the CLI logged in via a claude.ai subscription and no `ANTHROPIC_API_KEY` set, a test call returned JSON successfully in about 2s. Usage counts against the subscription's limits instead of being billed. Each call carries about 21k tokens of Claude Code overhead, so `4-spec` should keep calls lean and few.

## Build Order
The POC is built in stages. Each stage leaves the app usable for real on its own, so if time runs short there is still something coherent. The agents are the hardest and least certain part, so they come first.
1. **One challenge → Generate → Save/Discard:** create a challenge, run the creative agents, react to ideas with reasons. Everything is stored with its full history from the start. This stage also tests the core assumption: that multi-agent collaboration produces more original and useful ideas than a single rich prompt. Run the same challenge both ways and compare by gut, which also settles the "fewer, richer calls" tradeoff with evidence.
2. **Learning loop and Rework:** the next Generate uses past feedback; Rework sends an idea back to the agents.
3. **Library and Actions:** the Idea Library, Move to Action, Add feedback, and experiment tracking through to Completed.
4. **Multiple challenges and outcomes:** the challenge list, switching, closing or pausing, reopening, and the closing summary.
5. **Demo mode:** the fictional persona and separate demo database, for the video and screenshots.

*Revised in build (2026-10-25): the formal multi-agent vs single-prompt comparison was dropped; the learner had already compared them informally and found the collaborative agents clearly better.*

The data model is keyed to challenges from stage 1, so stage 4 is UI work, not a data migration.

## Technical Direction (preliminary, for `4-spec`)
Previewed and agreed in principle on 2026-10-18 and updated on 2026-10-19 for the challenge-first model. Not final; `4-spec` confirms or revises it once the PRD is approved.
- **Backend:** Python 3.12 + FastAPI (keeps the future Python analysis layer in the same codebase; Pydantic checks the shape of agent output).
- **Database:** SQLite + SQLModel. The key design choice is a single **append-only `events` table**: every save, discard, comment, rework, idea status change, outcome, and challenge status change (close, pause, reopen) is a timestamped row with structured reason tags. Each row links to a challenge, and optionally to an idea. Other tables: `challenges` (statement, optional context, status, outcome note), `ideas` and `generation_runs`, each linked to a challenge, plus a fixed list of reason tags.
- **Frontend:** server-rendered Jinja2 + HTMX, with no JS framework and no build step.
- **Agents:** `claude -p` subprocess behind a single `llm.py` adapter; techniques as files in `techniques/`, collaboration patterns as files in `patterns/`, an `orchestrator.py` that runs a pattern.
- **Learning boundary:** `context.py` is the only place that decides what history the agents see, so a Python analysis layer can replace it later.
- **Config:** generic reason tags, placeholder hints and any use-case wording sit in config files rather than code. Techniques and patterns stay generic.
- **Tooling:** uv + pytest.
- **Open tradeoff for the spec:** fewer, richer calls (simulated collaboration in one prompt, light on subscription limits) vs. a separate call per agent (real multi-agent collaboration, slower, uses limits faster). Also test CLI flags that cut the ~21k-token overhead per call.

## Portability Considerations (not POC requirements)
The proof of concept stays a local build. These are habits for `4-spec` and the build to follow where they cost little, so that packaging the app later (a one-command install or a one-click desktop app) doesn't need a rewrite. None of them adds a feature or delays the proof of concept.
- **Model provider behind the adapter:** `llm.py` is the only place that knows how agents are called. The Claude Code CLI is the only provider built now; an Anthropic API key (user's own key) or a hosted backend could be added later without touching the agents. This is the real portability blocker, because other users won't have Claude Code signed in to this subscription.
- **Data outside the code:** the database lives in a configurable data folder (ideally a per-user app-data location), not paths relative to the repository.
- **Definitions loaded as package files:** techniques, patterns, prompts and config ship inside the package and aren't found by relative path.
- **A single entry point:** one command starts the server and opens the browser.
- **Database access only through SQLModel:** this keeps a switch from SQLite to Postgres a configuration change if it ever becomes a hosted service. Explored on 2026-10-19: SQLModel adds little complexity (table classes double as Pydantic models, and it pairs naturally with FastAPI), and plain SQLAlchemy sits underneath if SQLModel's gaps, such as relationships, get in the way. On its own it doesn't guarantee an easy switch. These habits matter too:
  - no raw SQL; all queries go through SQLModel/SQLAlchemy;
  - timestamps stored as timezone-aware UTC;
  - reason tags in their own table or a SQLAlchemy `JSON` column, never comma-separated strings;
  - no reliance on SQLite's loose typing.
- **Schema migrations (open question for `4-spec`):** `create_all()` never alters existing tables, and "real use first" means the private database holds real data while the schema is still changing. The options are Alembic migrations (standard, more setup) or keeping the POC schema stable and handling a rare change with a small one-off script that copies the data into the new schema (a developer tool, not a user feature). A flexible append-only events table should keep schema changes rare. Leaning towards no Alembic for the POC, adding it before anyone else uses the app.
- **No OS-specific code:** paths and the CLI subprocess call work on Windows, macOS and Linux.
- **No frontend build step:** already the case with Jinja2 + HTMX, so the app can be wrapped in a desktop window (e.g. pywebview) as-is.

## Risks to Review Later
Raised on 2026-10-19 and parked on purpose. They don't change the POC scope. Revisit them during `3-prd` or after real use.
- **Feedback friction:** reasons on every Save and Discard only work if they take a tap or two. If they feel like a form, people skip them and the learning loop starves. One-tap reasons are likely the default, with the note optional.
- **Outcomes rarely get logged:** people try things and forget to come back, yet experiment outcomes are where the real value is. A light nudge may help (e.g. "You actioned this 7 days ago: how did it go?").
- **No grounding in real information:** without web research, ideas involving real companies or opportunities can be vague or invented. This is acceptable for the POC; web research (see Later) is the likely first addition afterwards.

## Later
- **Context reuse between challenges:** when starting a new challenge, choose which context from a past one to carry over (or start fresh).
- **Packaging:** first a uv-installable package (`uvx`/`uv tool install`, which downloads Python itself), then possibly a one-click desktop bundle (e.g. PyInstaller + pywebview) with bring-your-own API key. A hosted version would reopen the cuts on accounts and paid API use.
- **Export and import:** take a challenge out of the app as readable Markdown plus a full JSON history, and load it back in. Dropped from the POC on 2026-10-19, because everything lives in the app; worth revisiting if the app is packaged for others, who may want their data portable.
- **AI-suggested context updates** based on feedback and outcomes, applied only with the user's approval.
- **Python learning and analysis layer:** duplicate detection, pattern analysis, feedback filtering, context selection, and finding which techniques or combinations produce useful results. The aim is to avoid unnecessary AI calls by using ordinary code for analysis and retrieval, leaving Claude focused on creative generation and collaboration.
- More collaboration patterns (debate, chaining, critique rounds) and side-by-side comparison of patterns.
- Agents that research the web (real companies, real public problems) instead of only ideating.
- Richer Rework (e.g. turning an idea into a concrete step-by-step plan).
- Deployment beyond the local machine.
- Domain-specific tuning (tailored reason tags, hints and prompt framing per kind of challenge) if generic ones prove too blunt.

## Explicitly Cut
- **A persistent, cross-challenge user profile.** Context lives with the challenge. Reusing context between challenges comes later.
- **Guided profile questionnaire before first use.** It slows the start and most of it isn't needed to generate useful ideas.
- **Separate Tweak and Explore further actions.** Both sent an idea back to the agents with the user's input, so they are merged into one Rework action, available on new ideas and in the Library.
- **Domain-specific reason tags and hints.** They'd fit badly on other challenges; generic ones work everywhere.
- **Formal scoring or evaluation of ideas.** The user judges by gut ("I'll try it and see what happens").
- **Deleting ideas.** Discarding at any stage keeps the idea and its full history, because that information is valuable to future sessions.
- **Multi-user accounts and authentication.** It's a personal local tool, with one user.
- **Paid API usage.** This is a constraint for now and could be revisited later.
