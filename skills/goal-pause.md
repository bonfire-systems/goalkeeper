---
name: goal-pause
description: Pause the currently active goalkeeper goal without losing state. Use when the user invokes /goal-pause. The goal can later be resumed with /goal-resume.
---

You are operating the **goal-pause** skill.

## Flow

1. Read `.claude/goals/active.json`. If no active goal, tell the user and stop.
2. Read `.claude/goals/<slug>/state.json`.
3. If `state.status` is already `paused`, `done`, or `needs_human`, tell the user the current status and stop (no state change).
4. Set `state.status = paused`, add `paused_at: <ISO8601>`.
5. Append to `log.md`:
   ```
   ## <ISO8601> — paused
   Paused by user. No further iterations will run until /goal-resume.
   ```
6. Confirm to the user: "Paused goal `<slug>`. Resume with /goal-resume."

## Hard rules

- Do not cancel or alter any pending ScheduleWakeup. The wakeup prompt explicitly checks `state.status != active` and stops, so a stale wakeup is a no-op.
- Do not modify `rejection_count` or any other field besides `status` and `paused_at`.
- The log entry is append-only.
