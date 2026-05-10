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

### 6. Hand off to the goal skill

Re-enter the **goal** skill execution loop on the activated slug. Real work begins immediately in this turn.

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

- **More goals remain:** activate next.
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
  - **Update `.claude/goals/active.json` LAST** to point to `next_slug`:
    ```json
    {
      "slug": "<next_slug>",
      "activated_at": "<ISO8601>",
      "chain": "<chain name>"
    }
    ```
    Writing active.json last is intentional — it's the pointer used by every other skill to find the current goal. If steps 1-4 partially fail, leaving active.json pointing at the previous (now-done) slug is a more recoverable state than leaving it stale-pointing-at-next-with-no-state.json.
  - Re-enter the **goal** skill execution loop on `next_slug`. Real work begins immediately.

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
