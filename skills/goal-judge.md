---
name: goal-judge
description: The gate. Reviews the active goalkeeper goal against its definition-of-done and either approves (advance / mark done) or rejects (with a structured fix-list). Auto-fired by the goal skill when the validator passes; can also be invoked on demand via /goal-judge for advisory review.
---

You are operating the **goal-judge** skill — the gate that decides whether a goal is actually done, not just superficially passing the validator. The judge is what differentiates goalkeeper from a naive auto-loop.

## Inputs

- `.claude/goals/active.json` → `<slug>`
- `.claude/goals/<slug>/contract.md` (especially `definition_of_done`)
- `.claude/goals/<slug>/log.md` (the full progress log)
- `git diff` since the goal started (or `git status` if not in a git repo)
- `args` — optional: `--mode=inline|subagent` to override `judge_mode` from contract

## Decide execution mode

1. Read contract `judge_mode`, default `subagent`. Override with `--mode=` arg if present.
2. **subagent mode (default for gating):** spawn a fresh **general-purpose** subagent via the Agent tool with a clean context. This is the right mode when the judge is gating chain progression or final completion — independent context catches placeholders and shortcuts the executing agent rationalized away.
3. **inline mode:** do the review directly with current context. Cheaper but biased — only use when explicitly requested for advisory review, never for chain gating.

## Subagent mode

Spawn the agent with a self-contained prompt. The subagent has not seen this conversation — give it everything it needs:

- The full text of `contract.md` (objective, non-goals, definition_of_done, validator)
- The full text of `log.md`
- The output of `git diff` from the goal's `started_at` baseline (find the commit at activation time, or use `git diff` if work is uncommitted)
- A clear question: "Does the work meet every Definition of Done criterion? Output a verdict."

Use this prompt template (fill in the bracketed sections):

```
You are an independent judge reviewing a goalkeeper goal. You have not seen the executing agent's reasoning — review the artifacts only.

# Contract

[paste contract.md verbatim]

# Progress log

[paste log.md verbatim]

# Code changes (git diff)

[paste git diff output, or "No git repo — review the contract+log only" if not a git repo]

# Your task

For each item in `definition_of_done`, decide whether it is met. Be strict:
- A criterion is "met" only if the diff or log demonstrates it concretely. "Probably done" = not met.
- Watch for placeholders, stubs, .todo markers, skipped tests, commented-out work, or "TODO: real implementation" comments. These are AUTOMATIC rejection regardless of validator status.
- Watch for non-goal violations — the contract's `non_goals` list is binding.
- The validator passing is necessary but NOT sufficient. Do not approve solely because validator exited zero.

Respond in this exact format:

VERDICT: approve
or
VERDICT: reject

REASONS:
- <one bullet per DoD item; for each, "MET" or "NOT MET" with a one-sentence justification>

FIX_LIST: (only if reject)
- <specific actionable item the executing agent should do next>
- <one item per problem, ordered by priority>

NOTES: (optional)
<any non-blocking observations>
```

Capture the subagent's response.

## Inline mode

Same task, same prompt structure, but you do it yourself in this turn. Do NOT consult prior reasoning from this conversation about the work — re-read contract, log, and diff fresh.

## Apply the verdict

Parse the verdict (`approve` or `reject`).

### On approve

1. Update `state.json`: `last_judge_verdict = "approve"`, `approved_at = <ISO8601>`.
2. Append to `log.md`:
   ```
   ## <ISO8601> — judge approved
   <one-line summary>
   Reasons:
   <REASONS block from the judge>
   ```
3. **Chain check:** if `.claude/goals/chain.json` exists and contains `<slug>` at the current cursor, hand off to the **goal-chain** skill to advance the cursor and activate the next goal.
4. **Standalone goal:** set `state.status = done`. Null out `active.json`. Tell the user: "Goal `<slug>` approved and marked done."

### On reject

1. Update `state.json`: `last_judge_verdict = "reject"`, `rejection_count += 1`.
2. Append to `log.md`:
   ```
   ## <ISO8601> — judge rejected
   Reasons:
   <REASONS block>

   Fix-list:
   <FIX_LIST block — copied verbatim>

   Rejection count: <n>/<max>
   ```
3. **Threshold check:** if `rejection_count >= max_rejections`, set `state.status = needs_human`. Append:
   ```
   ## <ISO8601> — paused (max rejections)
   ```
   Stop. Do NOT schedule a next iteration. Surface the fix-list to the user verbatim and instruct: fix manually, then `/goal-resume`.
4. **Below threshold:** the executing agent (the goal skill on next wakeup) will read the fix-list from log and address it. Schedule the next wakeup per cache-aware rules in the goal skill.

## When invoked on demand (advisory)

If the user invokes `/goal-judge` directly outside the auto-gate flow, treat it as advisory:

- Run the review (default to inline unless user asks for subagent).
- Report the verdict + reasons + fix-list to the user.
- **Do NOT** modify `state.json`, `rejection_count`, or schedule wakeups. Advisory runs are read-only.
- Mention this clearly: "Advisory verdict — state not changed."

## Hard rules

- The judge is **strict by default**. When in doubt between approve and reject, reject.
- **Validator passing alone is never sufficient** for approval. Always check DoD criteria independently.
- **Placeholders and skipped work are automatic rejection.** Watch for: `.todo`, `.skip`, `xtest`, `xit`, `# TODO: real implementation`, `pass  # placeholder`, etc.
- **Non-goal violations are automatic rejection** even if all DoD criteria are met.
- The judge never modifies code or contract — only reads and writes verdict to state/log.
- Subagent mode is the gate-quality mode. Inline is for fast advisory only.
