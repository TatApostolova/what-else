---
doc: prd
status: approved
---

# What Else? — Product Requirements

A local creative studio where collaborating AI agents, each using a different creative-thinking technique, generate unconventional possibilities for a challenge you describe, and learn from your reactions until the challenge is resolved. Career exploration is the first use case.
Source: `scope.md > The Unique Kernel`, `scope.md > Built to Finish, Not to Keep You`.

This is a proof of concept. Every part is kept as simple as possible except the creative agents (`scope.md > The POC Boundary`). Interface details below are provisional MVP choices. Anything marked **(assumption)** was decided by the agent and can be revisited during the build without reopening this document.

## The Core Journey
Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like`.

1. **Arrive.** On first use you see a welcome screen with a one-line explanation of What Else? and a single prominent **Start a Challenge** button. On later visits you see the dashboard of existing challenges.
2. **Start a challenge.** Write a few sentences about the problem and, if you like, some free-text context (placeholder hints included; pasting a CV or notes is fine). Submit, and you land in the challenge workspace on the Explore tab.
3. **Generate.** Click **Generate**. The agents work together, and about 10 ideas appear, each labelled with the technique(s) that produced it.
4. **React** to each idea in Explore:
   - **Save** with one-tap reasons and an optional note. The idea moves to the Idea Library.
   - **Discard** with one-tap reasons and an optional note. It is stored, never deleted.
   - **Rework** with a note on what to change. A new, linked idea comes back into Explore for a fresh reaction.
   - Or leave it alone. Unreacted ideas stay in Explore.
5. **Develop saved ideas** in the Idea Library: Move to Action, Add feedback, Rework or Discard.
6. **Run experiments** in the Experiments tab: log what you're doing and your progress, then finish with a verdict (Worked / Partly worked / Didn't work / Dropped) and optional notes.
7. **Generate again.** The next batch draws on the challenge, its context and all its history, so it avoids straight repeats of rejected ideas and builds on what you liked and what worked.
8. **Finish.** Close the challenge as Achieved or Abandoned (optional note), or Pause it. A closing summary shows what was tried and what came of it. Any closed or paused challenge can be reopened with everything intact.

Success means the user finds an idea worth acting on, tries it, and closes the challenge feeling it achieved something.

## Screens and Layout

- **Welcome screen** (only when there are no challenges): name, one-line explanation, **Start a Challenge**.
- **New challenge form:** problem statement (required), context (optional, with placeholder hints), **Start**. It can be reached from the welcome screen and from the dashboard.
- **Dashboard:** a list of challenges showing each one's title (from the first line of the statement), status and last activity, plus a **New challenge** button. Active challenges come first, then Paused, then closed **(assumption)**. Clicking a challenge opens its workspace.
- **Challenge workspace:** one page per challenge.
  - **Header:** challenge statement and context in a panel that is collapsed by default and editable at any time, the challenge status, and the controls to close, pause or reopen. A link back to the dashboard.
  - **Three tabs:**
    - **Explore:** the Generate button, then new and reworked ideas waiting for a reaction, newest batch first.
    - **Idea Library:** saved ideas.
    - **Experiments:** actioned ideas, both running and finished.
  - Each tab shows a count of its ideas **(assumption)**.
- **Closing summary:** shown in the workspace when a challenge is Achieved or Abandoned, and viewable again later from the closed challenge.

## Look and Feel
Source: `scope.md > Inspiration & Identity`.

- Clean, light and card-based. Simple and friendly.
- Each idea is a card with its text and the technique label in the corner. If an idea came from several techniques collaborating, it shows all of them **(assumption)**.
- Primary action (Save) is a dark filled button, and Discard is an outlined button. Rework is a secondary/text-style button **(assumption)**.
- Feedback opens inline on the card ("Why isn't this idea right for you?" / "What do you like about it?"), with tag chips, an optional note and a submit button. No modal dialogs.
- Neutral sans-serif type, generous white space, one accent colour, and status shown as small coloured badges **(assumption)**.
- Avoid: dense dashboards, chat-bot styling, decorative gradients **(assumption)**.

## Features and Behavior

### Challenges
Source: `scope.md > Built to Finish, Not to Keep You`, `scope.md > The POC Boundary`.

- A challenge has a statement (required), context (optional), a status and an optional outcome note.
- The statement and context can be edited at any time. Edits affect the next Generate and don't change existing ideas.
- You can have several challenges at once and switch between them from the dashboard. Nothing is shared between challenges.
- Acceptance criteria:
  - [ ] With an empty database, the welcome screen appears. After one challenge exists, the dashboard appears instead.
  - [ ] Submitting a statement creates an Active challenge and opens its workspace on Explore.
  - [ ] Submitting an empty statement is blocked with a short message. Context can be left empty.
  - [ ] Editing the context and generating again produces ideas that reflect the change.
  - [ ] Ideas, feedback and experiments from challenge A never appear in challenge B.

### Generating Ideas
Source: `scope.md > The Unique Kernel`, `scope.md > The POC Boundary` (Creative agents, Learning loop).

- **Generate** runs the five technique agents (reverse thinking, random associations, analogies, SCAMPER, challenging assumptions) through one collaboration pattern in which they build on each other's ideas.
- Each run adds about 10 ideas to Explore (raised from 5 during the build, at the learner's request). Each idea shows its technique label(s).
- While it runs, the button is disabled and a "The agents are working…" indicator is shown. Generation can take a while, and that's acceptable **(assumption)**.
- Every generated idea is stored automatically with its technique, its run and its status history.
- Acceptance criteria:
  - [ ] Clicking Generate on a new challenge produces about 10 idea cards in Explore, each with a technique label.
  - [ ] The ideas are visibly shaped by the statement, and by the context if any was given.
  - [ ] Clicking Generate twice in a row is impossible while a run is in progress.

### Reacting to Ideas (Explore)
Source: `scope.md > The Core Loop` (step 3), `scope.md > Risks to Review Later` (Feedback friction).

- **Save:** choose one or more reason tags (one tap each) plus an optional note. The idea leaves Explore and appears in the Library. Saving with no tags and no note is allowed, so feedback never blocks the action **(assumption)**.
- **Discard:** same pattern, with discard reason tags. The idea leaves Explore and is kept in history with status Discarded.
- **Rework:** a short note on what to change (required, because it's the instruction) plus optional tags. The agents return **one** reworked idea, linked to the original, which appears in Explore for a fresh reaction. The original is kept with status Reworked and leaves Explore.
- **No reaction:** the idea stays in Explore. Inactivity is never treated as feedback.
- Reason tags are generic and come from config **(assumption: starting sets)**:
  - Save: "original", "practical", "fits me", "quick to try", "sparks other ideas".
  - Discard: "too vague", "not practical", "not me", "already tried", "too slow", "too much work" (added in build at the learner's request), "same as another idea" (added in `4-spec` to record agent convergence).
- Acceptance criteria:
  - [ ] Saving takes at most two taps when no note is added, and the idea immediately shows in the Library.
  - [ ] A discarded idea disappears from Explore and its reasons are stored.
  - [ ] A reworked idea arrives in Explore, visibly reshaped around the note, and shows that it was reworked from an earlier idea.
  - [ ] Ideas left unreacted are still in Explore after another Generate and after restarting the app.

### Idea Library
Source: `scope.md > The Core Loop` (step 4).

- Lists saved ideas with their technique labels, save reasons and notes.
- **Move to Action:** the idea moves to Experiments with status Actioned.
- **Add feedback:** add a note (and optional tags) without changing the status.
- **Rework:** same as in Explore. The reworked version appears in Explore. Because you already liked the original, it stays Saved in the Library **(assumption)**.
- **Discard:** with reasons and an optional note ("why you've changed your mind").
- **Add your own idea** (added in build at the learner's request): a title and optional description, added straight to the Library as Saved and labelled "YOUR IDEA". It has the same actions as agent ideas, and the agents see it in the history as the person's own idea. Reworking it credits both ("REVERSE THINKING ← YOUR IDEA").
- Each idea can expand to show its history: original text, feedback, comments and status changes, oldest first **(assumption: simple list)**.
- Acceptance criteria:
  - [ ] Move to Action moves the idea to Experiments.
  - [ ] Added feedback shows in the idea's history, and the idea stays in the Library.
  - [ ] A discarded Library idea leaves the Library, and its history is kept.

### Experiments
Source: `scope.md > The Core Loop` (step 4), `scope.md > The POC Boundary` (Idea Library).

- Shows actioned ideas. Running ones come first, then finished ones.
- **Log progress:** add dated free-text entries ("what I'm doing", "what happened so far").
- **Finish:** choose a verdict (Worked / Partly worked / Didn't work / Dropped) plus optional notes. The idea becomes Completed with that verdict. "Dropped" is a verdict, not a Discard, so the experiment still counts as tried **(assumption)**.
- Verdicts and notes feed future generations.
- Acceptance criteria:
  - [ ] Progress entries appear on the experiment with their dates, newest last.
  - [ ] Finishing with a verdict marks the experiment Completed and shows the verdict on its card.
  - [ ] A generation after a "Worked" or "Didn't work" verdict visibly takes it into account (e.g. builds on it or avoids it).

### Learning Loop
Source: `scope.md > The POC Boundary` (Learning loop; Learning logic kept separate), `scope.md > What "Working" Looks Like` (step 5).

- Every Generate and Rework receives the challenge statement, the context and a summary of this challenge's history: saves and discards with reasons, reworks, comments, experiment progress and verdicts.
- The agents avoid straight repeats of discarded ideas, but may reuse a useful element of one in a new direction.
- Unreacted ideas are not used as positive or negative signals.
- What history goes in is decided in one separate place, which starts simple (for example recent and relevant feedback).
- Acceptance criteria:
  - [ ] After discarding an idea with "already tried", the next Generate contains no idea that is essentially the same.
  - [ ] Over a few runs, at least one new idea visibly recombines an element of an earlier discarded or saved idea.

### Challenge Outcomes
Source: `scope.md > Built to Finish, Not to Keep You`, `scope.md > The Core Loop` (step 6).

- **Close as Achieved** or **Close as Abandoned**, each with an optional note. **Pause** has no note.
- **Closing summary** (built from stored data, with no AI call): the outcome and note, plus counts of ideas generated, saved, discarded, reworked and actioned, a list of experiments with their verdicts, and the saved ideas.
- **Reopen** returns any Achieved, Abandoned or Paused challenge to Active with everything intact.
- **While not Active**, the workspace is read-only: there is no Generate and no reactions, but everything can still be viewed. Saved and actioned ideas stay as they were. Reopening restores the full set of actions **(assumption)**.
- Every status change, including reopening, is recorded as an event.
- **Delete challenge** (added in build): after a confirmation prompt, permanently removes the challenge, its ideas, events and runs, and its entries in the private agent log.
- Acceptance criteria:
  - [ ] Closing as Achieved shows the summary with correct counts and the experiment verdicts.
  - [ ] A closed challenge shows its status on the dashboard and can't generate.
  - [ ] Reopening makes Generate and reactions available again, and nothing is lost.

### Demo Mode
*Cut during the build (learner decision): no seeded persona or demo flags. `WHATELSE_MODE=demo` still opens a separate, empty demo database with a "Demo" badge.*

Source: `scope.md > The POC Boundary` (Demo mode; Privacy by default).

- A setting starts the app on a separate demo database seeded with a fictional persona's challenge. The real database is never touched.
- A small "Demo" badge in the header makes the mode obvious **(assumption)**.
- Acceptance criteria:
  - [ ] Starting in demo mode shows only the demo challenge(s), and starting in normal mode shows only the real ones.
  - [ ] The demo flow in `scope.md > What "Working" Looks Like` can be performed end to end in about a minute, excluding generation wait time.

## States and Boundaries

- **First use:** the welcome screen with one action.
- **Empty Explore** (new challenge): a short prompt to click Generate.
- **Empty Library / Experiments:** one line explaining how ideas get there ("Save an idea in Explore to keep it here").
- **Generating:** an indicator is shown and Generate is disabled. The other tabs stay usable **(assumption)**.
- **Generation or Rework fails** (CLI error, subscription limit reached, malformed agent output): a plain message ("The agents couldn't finish. Try again in a moment."), with nothing lost and no partial ideas shown. For Rework, the original stays exactly where it was. The details go only to the private, git-ignored log.
- **Persistence:** everything persists across sessions and restarts. Nothing is ever deleted, and Discard only changes status.
- **Read-only challenge:** any non-Active challenge can be viewed but not changed until reopened.
- **Privacy:** the real database and agent logs live only in git-ignored local paths. Demo mode uses its own database.
- **Single user, local only:** no accounts and no login.

## Product Decisions

- **Welcome screen first, dashboard after.** First use gets one obvious action, and return visits go straight to resuming or creating.
- **One workspace per challenge with three tabs (Explore / Idea Library / Experiments).** Each stage of an idea's life has its own place.
- **Challenge statement and context collapsed at the top, editable anytime.** Context stays available without crowding the ideas.
- **Rework creates a new linked idea; the original is kept for history.** The reworked idea goes to Explore for a fresh reaction, so the full lineage is preserved for learning.
- **Experiment verdict: Worked / Partly worked / Didn't work / Dropped, plus optional notes.** It's a simple signal the agents can use as context.
- **Unreacted ideas stay in Explore, and inactivity is never feedback.** Preferences are only inferred from explicit reactions.
- **Simplest functional version of everything except the agents.** The goal is to build and test the product, not elaborate the workflow. The agent makes minor UI and edge-case calls and marks them as assumptions.

## What We're Building
Follows `scope.md > Build Order`. Each stage is usable on its own.

1. **Challenge → Generate → Save/Discard:** the welcome screen, the new-challenge form, the workspace with Explore, the five technique agents with one collaboration pattern, Save/Discard with tags and notes, and full history storage. Includes the multi-agent vs single-prompt comparison by gut. *(The single-prompt comparison was cut during the build: the learner had already compared the collaborative pattern against a single prompt informally and judged the collaborative ideas clearly better.)*
2. **Learning loop and Rework:** history fed into Generate, and Rework creating linked ideas.
3. **Idea Library and Experiments:** Move to Action, Add feedback, Rework and Discard from the Library, progress logs, and verdicts.
4. **Multiple challenges and outcomes:** the dashboard, switching, Close/Pause/Reopen, read-only state, and the closing summary.
5. **Demo mode:** the fictional persona, seeded demo database and badge.

## Deferred From the POC
- **Outcome nudges** ("You actioned this 7 days ago: how did it go?"). They're useful, but the loop must work first (`scope.md > Risks to Review Later`).
- **Web research / grounding in real companies.** This is the likely first addition after the POC.
- **Context reuse between challenges.** Each challenge starts fresh for now.
- **Export and import.** Everything lives in the app.
- **Editing or reordering reason tags in the UI.** They live in config.
- **Search, filter or sort within tabs.** The lists stay small in a POC.

## Possible Later Enhancements
- Packaging as a one-command install, then possibly a desktop app with bring-your-own API key.
- AI-suggested context updates, applied only with approval.
- A Python analysis layer that finds which techniques and combinations produce useful ideas, and replaces the simple learning component.
- More collaboration patterns and side-by-side comparison.
- Richer Rework, such as turning an idea into a step-by-step plan.
- Domain-specific reason tags and hints.

## Non-Goals
- **A persistent, cross-challenge user profile or guided questionnaire.** Context belongs to the challenge, and the start must stay fast.
- **Scoring ideas.** The user judges by gut.
- **Deleting ideas.** History is the learning material. *(Revised in build: a whole challenge can now be deleted permanently, with confirmation, at the learner's request. Challenges never share history, so this costs no other challenge anything.)*
- **Accounts, authentication and multi-user use.** It's a personal local tool.
- **Paid API usage.** Agents run on the existing subscription.
- **Job-search-specific logic in the core.** The challenge statement carries the framing.
- **Chat interface.** The interaction is cards and reactions, not conversation.

## Open Questions
- **Collaboration pattern and call budget** (one rich call vs a call per agent). This is a technical question for `4-spec`, settled by the stage-1 comparison. It doesn't block approval.
- **How the reworked idea shows its lineage** (e.g. "Reworked from: …" link). This can be settled during the build.
