---
name: goal-resume
description: Resume a paused or needs_human goalkeeper goal. Use when the user invokes /goal-resume after they've manually unblocked the goal (e.g. fixed a problem the judge flagged).
---

You are operating the **goal-resume** skill.

## Flow

1. Read `.claude/goals/active.json`. If no active goal, tell the user and stop.
2. Read `.claude/goals/<slug>/state.json`.
3. Branch on current status:
   - `active` — already running, no-op. Tell user.
   - `done` — already complete. Tell user; suggest `/goal-clear` to archive.
   - `paused` — proceed to step 4.
   - `needs_human` — the judge rejected too many times. Before resuming, **ask the user via AskUserQuestion** whether to:
     - **Reset rejection counter and continue (Recommended)** — user confirms they fixed the issues; reset `rejection_count = 0`.
     - **Continue without reset** — keep counter; one more rejection will re-trigger needs_human.
     - **Abandon** — route to `/goal-clear`.
4. Set `state.status = active`, set `resumed_at: <ISO8601>`. If the user opted to reset, also set `rejection_count = 0`.
5. Append to `log.md`:
   ```
   ## <ISO8601> — resumed
   Resumed by user.<conditional: " Rejection counter reset.">
   ```
6. Re-enter the **goal** skill execution loop immediately. Do not just schedule a wakeup — do real work in this turn.

## Hard rules

- Never silently reset the rejection counter. Always ask when resuming from `needs_human`.
- Never resume a `done` goal. Goals don't reopen — start a new contract instead.
- The log entry is append-only.
