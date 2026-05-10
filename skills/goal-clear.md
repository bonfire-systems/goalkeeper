---
name: goal-clear
description: Stop and archive the currently active goalkeeper goal. Use when the user invokes /goal-clear to abandon or finalize a goal. Files are moved to .claude/goals/_archive/, never deleted.
---

You are operating the **goal-clear** skill.

## Flow

1. Read `.claude/goals/active.json`. If no active goal, tell the user and stop.
2. Read `.claude/goals/<slug>/state.json` to capture final status.
3. **Confirm via AskUserQuestion** before archiving (unless the goal is already `done`):
   - **Archive and clear (Recommended)** — proceed.
   - **Cancel** — abort, no changes.
4. Append a final log entry:
   ```
   ## <ISO8601> — cleared
   Final status before clear: <status>. Rejection count: <n>. Archived.
   ```
5. **Move** (not copy) `.claude/goals/<slug>/` to `.claude/goals/_archive/<slug>-<YYYYMMDD-HHMMSS>/`. Use `mv` via Bash to preserve files atomically.
6. Set `.claude/goals/active.json` to `{"slug": null, "cleared_at": "<ISO8601>"}`.
7. **If a chain is active** (`.claude/goals/chain.json` exists and contains the cleared slug), set the chain status to `aborted` and append a chain-level log entry. Do NOT advance to the next goal — clearing kills the chain.
8. Tell the user: "Cleared goal `<slug>`. Archived to `.claude/goals/_archive/<dir>/`. Run /goal or /goal-prep to start a new one."

## Hard rules

- **Never delete files.** Always move to `_archive/`. The user may want to inspect the contract or log later.
- **Never proceed without confirmation** unless the goal is already `done` (in which case clear is just bookkeeping).
- **Clearing kills any active chain** — chains are not auto-resumed mid-stream.
- The log entry is append-only.
