---
name: goal-chain
description: Run a linear sequence of goalkeeper goals where the judge gates progression between them. Use when the user invokes /goal-chain "<file>" to start a chain. Also auto-invoked by the judge skill on approval to advance the chain cursor.
---

You are operating the **goal-chain** skill. A chain is a linear ordered list of goal slugs that execute one after another, gated by judge approval at each step.

## Modes

The skill operates in one of three modes determined by args and state:

1. **Start mode** — `args` is a non-empty path to a chain file. Begin a new chain.
2. **Advance mode** — invoked by the judge skill after approve. No args. Move cursor forward.
3. **Status mode** — `args == "status"` or chain exists and user asks plainly. Show progress.

## Start mode

Triggered by `/goal-chain "<path/to/chain.md>"`.

### 1. Parse chain file

The chain file is a markdown document with optional frontmatter and an ordered list of slugs. Accepted formats:

```markdown
---
name: my-chain-name
---

1. first-goal-slug
2. second-goal-slug
3. third-goal-slug
```

Or with bullets:

```markdown
- first-goal-slug
- second-goal-slug
```

Extract slugs from numbered list items or bullets. Trim whitespace. Strip any trailing comments after `#`.

### 2. Validate every slug has a contract

For each slug, verify `.claude/goals/<slug>/contract.md` exists. If any are missing, list them and stop. Tell the user to run `/goal-prep` for each missing slug, or remove them from the chain file.

### 3. Refuse to overlap

If `.claude/goals/active.json` shows an active goal, or `.claude/goals/chain.json` exists with status `active`, refuse and tell the user to `/goal-clear` first.

### 4. Write chain.json

Per the canonical chain.json shape (see goal.md "Canonical state shapes"):

```json
{
  "name": "<from frontmatter or filename>",
  "slugs": ["...", "..."],
  "cursor": 0,
  "status": "active",
  "started_at": "<ISO8601>",
  "completed_at": null,
  "source_file": "<absolute path to chain file>",
  "link_approvals": []
}
```

`link_approvals` starts empty and accumulates one entry per judge-approved link as the chain advances.

### 5. Activate the first slug

Write `.claude/goals/active.json` per the canonical active shape with `chain` populated:

```json
{
  "slug": "<slugs[0]>",
  "activated_at": "<ISO8601>",
  "chain": "<chain name>"
}
```

Initialize that goal's `state.json` per the canonical state.json shape (status=active, rejection_count=0, started_at=now, started_at_commit=`git rev-parse HEAD`, started_at_dirty_paths=`git status --porcelain`, chain_step=1). Append to its `log.md`:

```
## <ISO8601> — activated (chain step 1/<N>)
Chain: <name>. Starting first goal: <slug>.
```

### 6. Spawn the executor subagent

**v0.3+:** chains run their per-goal execution in a **fresh-context subagent** instead of the main conversation. Main context only orchestrates — spawning executor, spawning judge, applying verdict, advancing cursor. This is the load-bearing change that lets a chain run autonomously across many goals without main-context aging out.

Use the Agent tool with `subagent_type: general-purpose`. Pass a self-contained prompt:

1. **The full `contract.md`** — verbatim.
2. **The full `log.md`** — verbatim (so the executor sees the activation entry + any prior checkpoints if this is a re-spawn after judge rejection).
3. **Chain context** — chain name, current cursor position, total slugs, the prior link's approval timestamp.
4. **Repo state** — `git rev-parse HEAD`, `git status --porcelain` (first 20 lines).
5. **The directive** — verbatim, in this exact format:

```
You are the goalkeeper EXECUTOR SUBAGENT for goal `<slug>` (chain step <N>/<total>).

Your job: read the contract above, execute every Definition-of-Done item, run
the validator at the end, and return a structured summary. You operate in a
fresh context — you have no conversation history beyond this prompt. The
contract is your spec; do not improvise outside it.

Execution loop:
  1. Read the contract carefully. Identify the implementation work required.
  2. Do the work. Edit/write files as needed. Follow the contract's non-goals
     and anti-placeholder rule strictly.
  3. Append checkpoint entries to `.claude/goals/<slug>/log.md` as you go
     (one per logical sub-task or every ~5 file edits — whichever is more
     natural for the work).
  4. Run the validator: `<validator.command>`. Capture stdout+stderr.
  5. If validator FAILS: diagnose, fix, re-run. Repeat up to a reasonable
     attempt budget (~3-5 inner attempts). If still failing, document why
     in the log and return with status=blocked.
  6. If validator PASSES: append a "validator passed" entry to the log,
     update `.claude/goals/<slug>/state.json` with last_validator_result=pass
     and last_checkpoint_at, then return.

DO NOT spawn the judge yourself. The chain orchestrator handles that step.
DO NOT advance the chain cursor. DO NOT modify chain.json, active.json, or
the goals_completed list. DO NOT activate the next goal. Just do the work
for THIS goal and return.

Return ONCE with this structured output:

STATUS: validator_pass | validator_fail | blocked | needs_clarification

SUMMARY:
<3-8 sentences describing what you did: files touched, decisions made, any
non-obvious tradeoffs, anything the judge should pay particular attention to>

VALIDATOR_OUTPUT_TAIL:
<last ~40 lines of the validator's stdout+stderr — let the judge see the
actual pass/fail signal directly>

FILES_CHANGED:
<bulleted list of paths modified relative to repo root, plus brief one-line
note per file about what changed>

BLOCKERS: (only if status != validator_pass)
<specific reason: which DoD item, which file, what's missing or wrong>
```

### 7. Receive executor return, spawn judge

When the executor subagent returns its structured summary:

- **STATUS = blocked or needs_clarification** — append a `## <ISO8601> — executor blocked` entry to the goal's log with the BLOCKERS verbatim. Set `state.status = needs_human`. Pause chain (do NOT abort). Tell the user: "Executor subagent surfaced a blocker on `<slug>`: <one-line>. See `.claude/goals/<slug>/log.md`. Resolve and run `/goal-resume` to re-spawn the executor."

- **STATUS = validator_fail** — same as blocked, but the surface message names the failing validator path so the user knows it's a test/lint issue specifically.

- **STATUS = validator_pass** — spawn the judge per the `goal-judge` SKILL. Pass the executor's SUMMARY + VALIDATOR_OUTPUT_TAIL + FILES_CHANGED as part of the judge brief. The judge returns approve or reject.

### 8. Apply judge verdict

- **APPROVE:** advance per existing Advance mode (mark state.status=done, append link_approval, increment cursor, branch on end-of-chain or next goal).

- **REJECT:** the judge wrote a fix-list to the goal's log. Increment `state.rejection_count`. If under `max_rejections`, **re-spawn the executor subagent** with the original contract + log (which now includes the judge's fix-list) + an additional directive: "Address the judge's fix-list from the most recent `## <ISO8601> — judge rejected` block. Then proceed per the standard execution loop." Loop back to step 7.

- **REJECT exceeding max_rejections:** set `state.status = needs_human`, do NOT advance, surface to user.

## Advance mode

Triggered by the goal-judge skill after an approve verdict, when `chain.json` exists and contains the approved slug at the cursor.

**Atomic write order matters.** Follow these steps in this order so an interruption leaves a recoverable state (see "Recovery from interrupted advance" below):

### 1. Read chain.json and validate

Read `cursor` and `slugs`. Confirm `slugs[cursor]` matches the just-approved slug. If mismatch, abort and tell the user — chain state is corrupt; manual recovery needed.

### 2. Mark current goal done (and record link approval)

The just-approved goal: set `state.status = done` in its state.json. Leave its files in place (do NOT archive — chain artifacts stay for review).

The judge skill on approve already appended `{"slug": <approved>, "approved_at": <ISO>}` to `chain.json.link_approvals` before handing off. Verify the entry is present; if missing, append it now (defensive — handles the case where chain advance is invoked manually for recovery).

### 3. Increment cursor

`cursor += 1`. Write `chain.json` with the new cursor.

### 4. Branch on cursor

- **Cursor reached end (cursor == len(slugs)):** chain complete.
  - Set `chain.json`: `status=done`, `completed_at=<ISO8601>`.
  - Write `.claude/goals/active.json` to the canonical terminal shape:
    ```json
    {
      "slug": null,
      "ended_at": "<ISO8601>",
      "ended_reason": "chain_completed",
      "previous_slug": "<final slug approved>",
      "previous_chain": "<chain name>"
    }
    ```
  - Tell the user: "Chain `<name>` complete. <N> goals approved sequentially. See `chain.json.link_approvals` for per-link approval timestamps."
  - Stop.

- **More goals remain:** activate next + spawn executor subagent.
  - `next_slug = slugs[cursor]`.
  - **Capture a fresh git baseline for the next link** (HEAD has likely not moved, but dirty paths have grown to include the previous link's output):
    - `git rev-parse HEAD` → `started_at_commit`
    - `git status --porcelain` → `started_at_dirty_paths` (includes the previous link's output as pre-existing dirt for the next link's judge)
  - Initialize `next_slug`'s `state.json` per the canonical state.json shape (status=active, rejection_count=0, started_at=now, started_at_commit, started_at_dirty_paths, chain_step=cursor+1).
  - Append to `next_slug`'s `log.md`:
    ```
    ## <ISO8601> — activated (chain step <cursor+1>/<N>)
    Previous step approved. Starting: <next_slug>.
    Baseline commit: <short SHA>.
    Pre-existing dirty paths at activation: <list>.
    ```
  - **Update `.claude/goals/active.json`** to point to `next_slug`:
    ```json
    {
      "slug": "<next_slug>",
      "activated_at": "<ISO8601>",
      "chain": "<chain name>"
    }
    ```
    Writing active.json before spawning the executor is intentional — if the executor subagent crashes or is killed, active.json still points at the right slug and `/goal-resume` works.
  - **Spawn the executor subagent for `next_slug`** per Start-mode Step 6 above. Same prompt structure: contract + log + chain context + repo state + executor directive. When the executor returns, proceed per Start-mode Steps 7–8 (receive return, spawn judge, apply verdict, loop back here if more goals remain).

**Important — main context responsibilities:** the chain orchestrator NEVER does the per-goal implementation work itself. It only: spawns executor, receives executor return, spawns judge, receives judge verdict, writes state files, and either advances cursor or re-spawns executor (on judge reject within budget) or pauses (on max rejections / blocker). This keeps main context cost ~10K tokens per goal regardless of how big the goal's actual work was.

## Recovery from interrupted advance

If chain advance is interrupted mid-way (process crash, user `/clear`, etc.), the on-disk state can be inconsistent. Detect and recover:

**Symptom A — `chain.json.cursor` advanced but `active.json` still points at the previous (done) slug.**
- Diagnosis: step 5 (active.json update) didn't run.
- Recovery: read `chain.json.cursor`, derive `next_slug = slugs[cursor]`. If `<next_slug>/state.json` exists and shows `status=active`, just write `active.json` to point at it. If `state.json` is missing, treat as Symptom B.

**Symptom B — `chain.json.cursor` advanced but `<next_slug>/state.json` is missing.**
- Diagnosis: step 4's state.json initialization didn't run.
- Recovery: re-run advance steps 4 (next-link branch) and 5 fresh. The previous link is already marked done; the cursor is already incremented; safe to redo.

**Symptom C — `chain.json.cursor` not advanced but the previous link's `state.json` shows `status=done`.**
- Diagnosis: step 3 (cursor increment) didn't run.
- Recovery: increment cursor in chain.json and continue with steps 4-5.

**Symptom D — `chain.json.link_approvals` missing the latest approved link.**
- Diagnosis: step 2 entry was never appended (judge skill or chain skill missed it).
- Recovery: append `{"slug": <previous>, "approved_at": <state.approved_at from previous slug's state.json>}` to chain.json.link_approvals. Cosmetic only; doesn't block advance.

In all cases: never modify a `state.status=done` log retroactively. Add a new "## <ISO8601> — recovery" entry instead.

## Status mode

Print:

```
Chain:     <name>
Source:    <source_file>
Status:    <active|done|aborted>
Started:   <ISO8601>
Completed: <ISO8601 or "—">
Progress:  <cursor>/<N>
Goals:
  [x] <slug 1>  — done       approved <ISO8601>
  [>] <slug 2>  — active     rejections: <n>/<max>
  [ ] <slug 3>
  [ ] <slug 4>
```

Per-link `approved <ISO8601>` is read from `chain.json.link_approvals[]` (matched by slug). For the active link, show rejection count from its `state.json`. For pending links, show no detail.

Use plain ASCII markers `[x]` (done), `[>]` (active), `[ ]` (pending). No emoji.

## Interaction with goal-clear

If the user runs `/goal-clear` while a chain is active, the clear skill aborts the chain (sets `chain.json.status = aborted`) and does NOT advance. This is intentional — clearing means "stop everything."

## Hard rules

- **One chain at a time.** No nested or parallel chains.
- **Cursor only advances on judge approve.** Reject keeps the cursor in place; the goal skill handles retries within the rejection budget.
- **Don't archive chain goals on completion.** They form a traceable history; user can `/goal-clear` later if they want to archive.
- **Refuse to start a chain on top of an active goal.** Always require a clean slate.
- **A missing contract aborts chain start.** Do not auto-prep mid-chain — the user should prep all contracts up front so the chain definition is reviewable.
