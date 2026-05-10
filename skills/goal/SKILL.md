---
name: goal
description: Set or check status of a durable goalkeeper goal. Use this skill when the user invokes /goal "<objective>" to start a new contract-driven goal, or /goal with no arguments to see status of the currently active goal. Goalkeeper goals run autonomously across many turns with checkpoint validation and judge-gated completion.
---

You are operating the **goalkeeper** skill — durable, contract-driven goal execution with judge-gated completion. This skill is invoked when the user runs `/goal` or `/goal "<objective>"`.

## Canonical state shapes

Single source of truth for the JSON files goalkeeper reads and writes. Other skills (goal-clear, goal-judge, goal-chain) MUST conform to these shapes — drift here is the source of cross-skill bugs.

### `.claude/goals/active.json`

Two shapes only — active or terminal.

**Active** (a goal is currently running):
```json
{
  "slug": "<slug>",
  "activated_at": "<ISO8601>",
  "chain": "<chain-name>"
}
```
The `chain` field is OPTIONAL — present only when activation was driven by `/goal-chain` (start mode or advance mode). Standalone goals omit it.

**Terminal** (no active goal):
```json
{
  "slug": null,
  "ended_at": "<ISO8601>",
  "ended_reason": "done" | "cleared" | "chain_completed" | "aborted",
  "previous_slug": "<slug>",
  "previous_chain": "<chain-name>"
}
```
`slug`, `ended_at`, and `ended_reason` are REQUIRED on terminal. `previous_slug` SHOULD be set when the last activity was a single goal or chain link. `previous_chain` SHOULD be set when a chain just ended (`chain_completed` or `aborted`).

### `.claude/goals/<slug>/state.json`

```json
{
  "status": "active" | "paused" | "done" | "needs_human",
  "rejection_count": <int>,
  "started_at": "<ISO8601>",
  "started_at_commit": "<git rev-parse HEAD or null>",
  "started_at_dirty_paths": ["<paths from git status --porcelain at activation>"],
  "chain_step": <int>,
  "last_checkpoint_at": "<ISO8601 or null>",
  "last_validator_result": "pass" | "fail: <reason>" | null,
  "last_judge_verdict": "approve" | "reject" | null,
  "approved_at": "<ISO8601>",
  "paused_at": "<ISO8601>",
  "resumed_at": "<ISO8601>",
  "needs_human_at": "<ISO8601>",
  "validator_baseline_result": "pass" | "fail" | "not_runnable" | null,
  "validator_baseline_failing_paths": ["<path>"]
}
```
`status`, `rejection_count`, `started_at`, `started_at_commit`, `started_at_dirty_paths` are REQUIRED on activation. `chain_step` SHOULD be present when the goal is part of a chain (denormalized for log clarity; chain.json is the source of truth for cursor). Timestamp fields populate as the goal transitions: `approved_at` on judge approve, `paused_at`/`resumed_at` on `/goal-pause`/`/goal-resume`, and `needs_human_at` when `rejection_count` reaches `max_rejections` and status flips to `needs_human`.

`validator_baseline_result` and `validator_baseline_failing_paths` are populated by `/goal-prep` if it ran the validator once at activation baseline (which prep already does to confirm the command is runnable). When set, the judge treats `failing_paths` as pre-existing — a goal-end validator failure on those same paths is not the goal's fault. When null (validator was not run at prep, or prep is skipped), the judge has no pre-existing baseline to subtract from and treats validator failures as goal-caused.

### `.claude/goals/chain.json`

```json
{
  "name": "<chain name>",
  "slugs": ["<slug>", "..."],
  "cursor": <int>,
  "status": "active" | "done" | "aborted",
  "started_at": "<ISO8601>",
  "completed_at": "<ISO8601 or null>",
  "source_file": "<absolute path>",
  "link_approvals": [
    {"slug": "<slug>", "approved_at": "<ISO8601>"}
  ]
}
```
`link_approvals` accumulates one entry per judge-approved link. Provides chain-level visibility independent of per-link state.json files.

## Decide mode from args

- `args` non-empty → **set mode** (start or resume a goal)
- `args` empty → **status mode** (report on active goal)

## Status mode

1. Read `.claude/goals/active.json`. If missing or `slug` is null, output: `No active goal. Run /goal-prep "<rough idea>" or /goal "<objective>" to start one.` and stop.
2. Read `.claude/goals/<slug>/contract.md`, `state.json`, and the last 10 entries of `log.md`.
3. Print a compact status block:

   ```
   Goal:        <slug>
   Objective:   <one-line>
   Status:      <status>   Rejections: <n>/<max>
   Started:     <ISO8601>   Elapsed: <human readable>
   Validator:   <last_validator_result>
   Judge:       <last_judge_verdict>
   Last log:    <timestamp> — <one-line summary>
   ```

4. If `status == needs_human`, surface the latest judge fix-list verbatim and tell the user: fix the listed items, then run `/goal-resume` to continue or `/goal-clear` to abandon.

## Set mode

1. **Derive slug:** extract or generate a kebab-case slug from the objective (≤64 chars, lowercase, alphanumeric and hyphen only). If the user passed an explicit `--slug=<value>`, use that.

2. **Contract resolution:**
   - If `.claude/goals/<slug>/contract.md` exists, treat the request as a resume: skip prep, jump to step 3.
   - If it does not exist, **auto-route to `/goal-prep`** with the same objective. Do not write a thin one-line contract — prep is mandatory because the contract IS the spec. After prep completes and writes the contract, return here.

3. **Activate:**
   - Ensure `.claude/goals/` exists. If creating it for the first time, also create `.claude/goals/.gitignore` containing `*` and `!shared/` and `!.gitignore` so personal goals stay private but a `shared/` subdir can be opt-in committed.
   - **Capture the git baseline.** If the working directory is a git repo (`git rev-parse --is-inside-work-tree` succeeds), capture `git rev-parse HEAD` as the goal's diff origin. If the tree is dirty, also capture `git status --porcelain` as a snapshot of the dirty paths so the judge can distinguish goal work from pre-existing changes. If not in a git repo, set both fields to `null`.
   - Write `.claude/goals/<slug>/state.json`:
     ```json
     {
       "status": "active",
       "rejection_count": 0,
       "started_at": "<ISO8601 now>",
       "started_at_commit": "<git rev-parse HEAD or null>",
       "started_at_dirty_paths": ["<paths from git status --porcelain at activation>"],
       "last_checkpoint_at": null,
       "last_validator_result": null,
       "last_judge_verdict": null
     }
     ```
   - Write `.claude/goals/active.json` per the canonical active shape. If the activation is driven by `/goal-chain`, include `"chain": "<chain-name>"`; otherwise omit the field.
   - Append to `log.md`:
     ```
     ## <ISO8601> — activated
     Starting work on: <objective>
     Baseline commit: <short SHA or "no-git">
     ```

4. **Begin the execution loop** (next section).

## Execution loop

This block runs on activation AND on every ScheduleWakeup re-entry.

1. Read the active contract: `.claude/goals/active.json` → `<slug>` → `contract.md` and `state.json`.
2. If `state.status != active`, stop. Do not schedule another wakeup.
3. Read recent log entries to know where work left off.
4. **Do real work** on the objective for one checkpoint's worth of progress (size per `checkpoint_cadence` in the contract — e.g. ~5 file edits, ~20 minutes of effort, or one logical sub-task).
5. **Checkpoint:** append to `log.md`:
   ```
   ## <ISO8601> — checkpoint
   <one short paragraph: what changed, files touched, decisions made, what's next>
   ```
6. **Run validator:** execute `validator.command` from frontmatter. Capture stdout+stderr. Honor `timeout_seconds`. Interpret per `validator.success` (default `exit_zero`). Update `state.last_validator_result` to one of `pass`, `fail: <short reason>`. Update `state.last_checkpoint_at`.

7. **Branch on validator:**
   - **Failed:** append a one-line failure summary to log. Schedule next iteration via `ScheduleWakeup` with delay from `wakeup_seconds` (contract) or pick cache-aware default (see below). Wakeup prompt:
     ```
     Continue active goalkeeper goal — read .claude/goals/active.json and proceed per the goal skill execution loop.
     ```
   - **Passed:** invoke the **goal-judge** skill (do this by writing a sentinel `.claude/goals/<slug>/.judge-pending` and immediately running the judge skill in this same turn). Judge will read contract + `git diff` + log and return approve/reject.

8. **Branch on judge verdict** (judge writes verdict to `state.last_judge_verdict` and a fix-list to `log.md` if reject):
   - **Approve:**
     - If `.claude/goals/chain.json` exists and contains the active slug at the cursor, defer to the **goal-chain** skill to advance the cursor and activate the next goal.
     - Otherwise: set `state.status=done`, append `## <ISO8601> — done` to log, null out `active.json` (`{"slug": null}`). Surface a one-paragraph completion summary to the user.
   - **Reject:**
     - Append the judge's fix-list to log under `## <ISO8601> — judge rejected`.
     - `state.rejection_count += 1`.
     - If `rejection_count >= max_rejections` (default 5): set `state.status=needs_human`, append `## <ISO8601> — paused (max rejections)`, stop. Do NOT schedule next wakeup. Surface to user.
     - Otherwise: schedule next iteration with the fix-list as the next turn's primary task. Wakeup prompt:
       ```
       Continue active goalkeeper goal — judge rejected the last attempt. Read the most recent "judge rejected" block in .claude/goals/<slug>/log.md and address each fix-list item. Then proceed per the goal skill execution loop.
       ```

## Cache-aware wakeup delay

The Anthropic prompt cache has a 5-minute TTL. Pick `delaySeconds` deliberately:

- **60–270s** — validator runs fast, cache stays warm. Right for tight iteration.
- **1200–1800s** — validator is slow (long test suites, builds, evals) or work is genuinely idle.
- **Avoid 300s** — pays cache miss without amortizing it.
- Honor `wakeup_seconds` from the contract verbatim if set.
- The runtime clamps to [60, 3600].

## Hard rules

- **Never modify `contract.md` mid-run.** If the spec is wrong, stop and ask the user to amend it explicitly via /goal-clear + new prep.
- **Never skip the validator.** Never declare "done" without judge approval.
- **The log is append-only.** Never delete or rewrite past entries.
- **One execution loop per goal.** Do not spawn parallel iterations on the same slug.
- **Rejection counter only resets** on judge approval or `/goal-clear`.
- **Anti-placeholder:** do not stub, mock, or skip work to make the validator pass. The judge will catch placeholders and reject. (Borrowed from the Ralph pattern.)
