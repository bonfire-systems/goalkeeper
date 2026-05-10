---
name: goal-judge
description: The gate. Reviews the active goalkeeper goal against its definition-of-done and either approves (advance / mark done) or rejects (with a structured fix-list). Auto-fired by the goal skill when the validator passes; can also be invoked on demand via /goal-judge for advisory review.
---

You are operating the **goal-judge** skill — the gate that decides whether a goal is actually done, not just superficially passing the validator. The judge is what differentiates goalkeeper from a naive auto-loop.

## Inputs

- `.claude/goals/active.json` → `<slug>`
- `.claude/goals/<slug>/contract.md` (especially `definition_of_done`)
- `.claude/goals/<slug>/log.md` (the full progress log)
- `state.started_at_commit` — git baseline captured at activation; use as the diff origin
- `state.started_at_dirty_paths` — paths that were already dirty at activation; the judge should NOT credit/blame those
- `args` — optional: `--mode=inline|subagent` to override `judge_mode` from contract

## Compute the diff scope

Run `git diff <state.started_at_commit>..HEAD` AND `git diff` (working tree) to capture both committed and uncommitted goal work. If `started_at_commit` is null (not a git repo), fall back to `git status` if available, otherwise note "no-git".

**Default exclusion globs** — apply via `git diff -- ':!<glob>'` to keep noise out of the judge's context:

- Lockfiles: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`, `go.sum`, `Gemfile.lock`, `composer.lock`
- Build outputs: `dist/`, `build/`, `out/`, `target/`, `.next/`, `*.min.js`, `*.min.css`
- Test/coverage: `coverage/`, `.nyc_output/`, `test-results/`
- IDE/editor: `.vscode/`, `.idea/`, `.DS_Store`

If the contract has a `diff_excludes` field, append those globs as well.

If the contract has a `diff_includes` field (rare — for narrowing), prefer that over the default-minus-excludes.

**Pre-existing-dirt subtraction:** any file in `state.started_at_dirty_paths` that the judge sees in the diff should be flagged as "pre-existing — verify these changes belong to the goal." Don't auto-credit them as goal work.

## Decide execution mode

1. Read contract `judge_mode`, default `subagent`. Override with `--mode=` arg if present.
2. **subagent mode (default for gating):** spawn a fresh **general-purpose** subagent via the Agent tool with a clean context. This is the right mode when the judge is gating chain progression or final completion — independent context catches placeholders and shortcuts the executing agent rationalized away.
3. **inline mode:** do the review directly with current context. Cheaper but biased — only use when explicitly requested for advisory review, never for chain gating.

## Subagent mode

Spawn the agent with a self-contained prompt. The subagent has not seen this conversation — give it everything it needs.

Before constructing the prompt, compute:
- The diff (per "Compute the diff scope" above), with default + contract exclusions applied
- The list of files modified or added by the goal, derived from `git diff --name-only` over the same scope

The judge subagent must do BOTH of these — diffs lose context (renames, surrounding code, file-level structure):
1. **Read the diff** for an overview of what changed
2. **Read each modified/added file end-to-end** via the Read tool to verify behavior, not just surface

Use this prompt template (fill in the bracketed sections):

```
You are an independent judge reviewing a goalkeeper goal. You have not seen the executing agent's reasoning — review the artifacts only.

# Contract

[paste contract.md verbatim]

# Progress log

[paste log.md verbatim]

# Diff scope

Baseline: [started_at_commit short SHA or "no-git"]
Default + contract exclusions applied (lockfiles, build outputs, coverage, IDE files).
Pre-existing dirty paths at activation (do NOT credit as goal work, but flag if any goal work touched them):
  [list from state.started_at_dirty_paths, or "none"]

# Files modified or added since baseline

[absolute path list, one per line]

# Diff (excerpt)

[paste filtered git diff output, or "No git repo — review log + files only" if not a git repo]

# Your task

For each item in `definition_of_done`, decide whether it is met. Use BOTH the diff above AND the Read tool to read each modified/added file in full — diffs hide context. Be strict:

- A criterion is "met" only if the diff or files demonstrate it concretely. "Probably done" = not met.
- Watch for placeholders, stubs, .todo markers, skipped tests, commented-out work, or "TODO: real implementation" comments. These are AUTOMATIC rejection regardless of validator status.
- Watch for tests that assert on existence rather than behavior (`expect(fn).toBeDefined()` is not a test).
- Watch for non-goal violations — the contract's `non_goals` list is binding.
- Watch for changes to pre-existing dirty paths that may not be the goal's intent.
- The validator passing is necessary but NOT sufficient. Do not approve solely because validator exited zero.

Respond in this exact format:

VERDICT: approve
or
VERDICT: reject

REASONS:
- <one bullet per DoD item; for each, "MET" or "NOT MET" with a one-sentence justification grounded in a specific file/line>
- Non-goal violations: NONE / <list>
- Anti-placeholder check: CLEAN / <findings>
- Pre-existing-dirt check: NONE / <list of suspicious paths>

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
