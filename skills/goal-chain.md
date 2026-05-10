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

```json
{
  "name": "<from frontmatter or filename>",
  "slugs": ["...", "..."],
  "cursor": 0,
  "status": "active",
  "started_at": "<ISO8601>",
  "completed_at": null,
  "source_file": "<absolute path to chain file>"
}
```

### 5. Activate the first slug

Set `.claude/goals/active.json` to point to `slugs[0]`. Initialize that goal's `state.json` (status=active, rejection_count=0, started_at=now). Append to its `log.md`:

```
## <ISO8601> — activated (chain step 1/<N>)
Chain: <name>. Starting first goal: <slug>.
```

### 6. Hand off to the goal skill

Re-enter the **goal** skill execution loop on the activated slug. Real work begins immediately in this turn.

## Advance mode

Triggered by the goal-judge skill after an approve verdict, when `chain.json` exists and contains the approved slug at the cursor.

### 1. Read chain.json

Read `cursor` and `slugs`. Confirm `slugs[cursor]` matches the just-approved slug. If mismatch, abort and tell the user — chain state is corrupt; manual recovery needed.

### 2. Mark current goal done

The just-approved goal: set `state.status = done` in its state.json. Leave its files in place (do NOT archive — chain artifacts stay for review).

### 3. Increment cursor

`cursor += 1`.

### 4. Branch on cursor

- **Cursor reached end (cursor == len(slugs)):** chain complete.
  - Set `chain.json`: `status=done`, `completed_at=<ISO8601>`.
  - Set `.claude/goals/active.json` to `{"slug": null, "chain_completed_at": "<ISO8601>"}`.
  - Tell the user: "Chain `<name>` complete. <N> goals approved sequentially."
  - Stop.

- **More goals remain:** activate next.
  - `next_slug = slugs[cursor]`.
  - Set `.claude/goals/active.json` to point to `next_slug`.
  - Initialize `next_slug`'s `state.json` (status=active, rejection_count=0, started_at=now, chain_step=cursor+1).
  - Append to `next_slug`'s `log.md`:
    ```
    ## <ISO8601> — activated (chain step <cursor+1>/<N>)
    Previous step approved. Starting: <next_slug>.
    ```
  - Re-enter the **goal** skill execution loop on `next_slug`. Real work begins immediately.

## Status mode

Print:

```
Chain:     <name>
Source:    <source_file>
Status:    <active|done|aborted>
Progress:  <cursor>/<N>
Goals:
  [✓] <slug 1>  — done
  [→] <slug 2>  — active   (rejections: <n>/<max>)
  [ ] <slug 3>
  [ ] <slug 4>
```

Use plain ASCII markers (no emoji unless the user enables them globally).

## Interaction with goal-clear

If the user runs `/goal-clear` while a chain is active, the clear skill aborts the chain (sets `chain.json.status = aborted`) and does NOT advance. This is intentional — clearing means "stop everything."

## Hard rules

- **One chain at a time.** No nested or parallel chains.
- **Cursor only advances on judge approve.** Reject keeps the cursor in place; the goal skill handles retries within the rejection budget.
- **Don't archive chain goals on completion.** They form a traceable history; user can `/goal-clear` later if they want to archive.
- **Refuse to start a chain on top of an active goal.** Always require a clean slate.
- **A missing contract aborts chain start.** Do not auto-prep mid-chain — the user should prep all contracts up front so the chain definition is reviewable.
