---
name: goal-judge
description: The gate. Reviews the active goalkeeper goal against its definition-of-done and either approves (advance / mark done) or rejects (with a structured fix-list). Auto-fired by the goal skill when the validator passes (inline mode), or invoked by the goal-chain orchestrator after executor subagent returns (subagent mode, v0.3+). Can also be invoked on demand via /goal-judge for advisory review.
---

You are operating the **goal-judge** skill — the gate that decides whether a goal is actually done, not just superficially passing the validator. The judge is what differentiates goalkeeper from a naive auto-loop.

## Invocation sources (v0.3+)

The judge is invoked from one of three places:

1. **Inline mode** — `/goal` skill's execution loop auto-fires the judge when the validator passes (the historical default).
2. **Subagent mode** — `/goal-chain` orchestrator invokes the judge AFTER the executor subagent returns with `STATUS: validator_pass`. The executor never invokes the judge itself; that responsibility moved up to the chain orchestrator in v0.3.
3. **Advisory on-demand** — user runs `/goal-judge` directly for a non-binding read on an in-progress goal (does not advance state).

The verdict logic and grading rubric are identical across all three sources. Only the invocation context differs.

## Inputs

- `.claude/goals/active.json` → `<slug>`
- `.claude/goals/<slug>/contract.md` (especially `definition_of_done`)
- `.claude/goals/<slug>/log.md` (the full progress log)
- `state.started_at_commit` — git baseline captured at activation; use as the diff origin
- `state.started_at_dirty_paths` — paths that were already dirty at activation; the judge should NOT credit/blame those
- `state.validator_baseline_result` — `"pass" | "fail" | "not_runnable" | null` — was the validator passing at activation? Captured by `/goal-prep`.
- `state.validator_baseline_failing_paths` — paths the validator flagged at baseline; if the final validator failure is on these same paths, it's pre-existing dirt, not goal-caused
- `args` — optional: `--mode=inline|subagent` to override `judge_mode` from contract
- **Subagent-mode extra context** — when invoked by `/goal-chain` after executor return, the orchestrator passes the executor's structured summary (STATUS, SUMMARY, VALIDATOR_OUTPUT_TAIL, FILES_CHANGED, BLOCKERS) as additional context. The judge uses this as a leading hint but MUST still independently verify against the contract — the executor's self-report is not authoritative.

## Build the judge prompt — mechanical assembly

Don't improvise this. Each judge invocation must produce the same prompt-shape so verdicts are comparable across runs.

### Step 1 — read state

```
slug         = <read .claude/goals/active.json>.slug
state        = <read .claude/goals/<slug>/state.json>
contract_md  = <read .claude/goals/<slug>/contract.md verbatim>
log_md       = <read .claude/goals/<slug>/log.md verbatim>
```

### Step 2 — assemble the exclusion pathspecs

Default exclusions (always apply):

```
DEFAULT_EXCLUDES=(
  ':!package-lock.json' ':!yarn.lock' ':!pnpm-lock.yaml'
  ':!Cargo.lock' ':!poetry.lock' ':!go.sum'
  ':!Gemfile.lock' ':!composer.lock'
  ':!dist/**' ':!build/**' ':!out/**' ':!target/**' ':!.next/**'
  ':!**/*.min.js' ':!**/*.min.css'
  ':!coverage/**' ':!.nyc_output/**' ':!test-results/**'
  ':!.vscode/**' ':!.idea/**' ':!.DS_Store'
)
```

Append contract `diff_excludes` if present (each entry becomes `:!<glob>`).

If contract has `diff_includes` (rare narrowing), use those positively instead of default-minus-excludes — e.g. `git diff <baseline>..HEAD -- packages/api/ packages/web/`.

### Step 3 — compute the diff

If `state.started_at_commit` is non-null (git repo):

```bash
# Committed work since baseline
git diff <state.started_at_commit>..HEAD -- "${DEFAULT_EXCLUDES[@]}" <user_excludes...>

# Uncommitted working-tree work (staged + unstaged)
git diff -- "${DEFAULT_EXCLUDES[@]}" <user_excludes...>

# Untracked new files (not shown by git diff)
git ls-files --others --exclude-standard -- "${DEFAULT_EXCLUDES[@]}"
```

Concatenate the three outputs in that order. For untracked new files, also Read them so the judge sees their full content (not just the path list).

If `state.started_at_commit` is null (not a git repo): use `git status` if available; otherwise note "no-git — review log + files only" in the prompt.

### Step 4 — compute the file list

```bash
# Modified files (committed + uncommitted)
git diff --name-only <state.started_at_commit>..HEAD -- "${DEFAULT_EXCLUDES[@]}" <user_excludes...>
git diff --name-only -- "${DEFAULT_EXCLUDES[@]}" <user_excludes...>

# Untracked
git ls-files --others --exclude-standard -- "${DEFAULT_EXCLUDES[@]}"
```

Dedupe and absolutize (prefix with the repo root). This is the file list the judge subagent must Read end-to-end.

### Step 5 — pre-existing-dirt subtraction

For each path in `state.started_at_dirty_paths`: if the path also appears in step 4's file list, mark it for the judge as "pre-existing — verify these changes belong to the goal." Do NOT remove it from the file list (the judge still inspects it), just flag it. The judge's `Pre-existing-dirt check` verdict line addresses this set explicitly.

### Step 6 — pre-existing validator-failure subtraction

If `state.validator_baseline_result == "fail"`, the validator was ALREADY failing at activation. Capture the current validator failure paths and compare:

- **Goal-caused failure:** current failing path is NOT in `state.validator_baseline_failing_paths`, OR `state.validator_baseline_result` was `"pass"`. → blocks approval.
- **Pre-existing failure:** current failing path IS in `state.validator_baseline_failing_paths` AND the goal did not modify it (not in step 4 file list). → does NOT block approval if all DoD items are otherwise met. Surface in NOTES so the user can decide whether to fix opportunistically.

When `validator_baseline_result == null` (prep didn't run the validator, or the goal was activated without prep), the judge has no baseline to subtract from — treat all validator failures as goal-caused. The user can manually amend state.json if they know better.

## Decide execution mode

1. Read contract `judge_mode`, default `subagent`. Override with `--mode=` arg if present.
2. **subagent mode (default for gating):** spawn a fresh **general-purpose** subagent via the Agent tool with a clean context. This is the right mode when the judge is gating chain progression or final completion — independent context catches placeholders and shortcuts the executing agent rationalized away.
3. **inline mode:** do the review directly with current context. Cheaper but biased — only use when explicitly requested for advisory review, never for chain gating.

## Subagent mode

Spawn the agent with a self-contained prompt assembled from steps 1-5 above. The subagent has not seen this conversation — give it everything it needs.

The judge subagent must do BOTH of these — diffs lose context (renames, surrounding code, file-level structure):
1. **Read the diff** for an overview of what changed
2. **Read each modified/added file end-to-end** via the Read tool to verify behavior, not just surface

Use this prompt template (fill in the bracketed sections from steps 1-5):

```
You are an independent judge reviewing a goalkeeper goal. You have not seen the executing agent's reasoning — review the artifacts only.

# Contract

[paste contract.md verbatim]

# Progress log

[paste log.md verbatim]

# Diff scope

Baseline: [started_at_commit short SHA or "no-git"]
Validator baseline: [state.validator_baseline_result or "unknown"]
Pre-existing validator-failing paths (failures on these are NOT goal-caused):
  [list from state.validator_baseline_failing_paths, or "none/unknown"]
Default + contract exclusions applied (lockfiles, build outputs, coverage, IDE files).
Pre-existing dirty paths at activation (do NOT credit as goal work, but flag if any goal work touched them):
  [list from state.started_at_dirty_paths, or "none"]

# Files modified or added since baseline

[absolute path list, one per line]

# Diff (excerpt)

[paste filtered git diff output, or "No git repo — review log + files only" if not a git repo]

# Your task

**Output the verdict ONCE.** Pre-think your reasoning before producing the structured response. Do not self-correct or revise individual DoD lines mid-response — finalize each MET/NOT MET decision before writing the verdict block.

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
- Pre-existing validator-failure check: NONE / <list of paths failing at baseline that still fail; mark "not goal-caused">

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
3. **Chain check:** if `.claude/goals/chain.json` exists and contains `<slug>` at the current cursor, **append** to `chain.json.link_approvals`:
   ```json
   {"slug": "<slug>", "approved_at": "<ISO8601 now>"}
   ```
   Then hand off to the **goal-chain** skill to advance the cursor and activate the next goal. (The goal-chain skill is responsible for setting `chain.json.status = done` and writing the terminal active.json when the cursor reaches the end.)
4. **Standalone goal:** set `state.status = done`. Write `.claude/goals/active.json` to the canonical terminal shape (see goal.md "Canonical state shapes"):
   ```json
   {
     "slug": null,
     "ended_at": "<ISO8601 now>",
     "ended_reason": "done",
     "previous_slug": "<slug>"
   }
   ```
   Tell the user: "Goal `<slug>` approved and marked done."

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
3. **Threshold check:** if `rejection_count >= max_rejections`, set `state.status = needs_human` and `state.needs_human_at = <ISO8601 now>`. Append:
   ```
   ## <ISO8601> — paused (max rejections)
   ```
   Stop. Do NOT schedule a next iteration. Do NOT modify `active.json` — it stays in active shape because `needs_human` is paused-awaiting-human, not termination. Surface the fix-list to the user verbatim and instruct: fix manually, then `/goal-resume` (which will ask whether to reset the rejection counter).
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
