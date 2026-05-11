# Reject-cycle demo — full transcript

Real reject-then-approve cycle on a benchmark test in a private TypeScript codebase. **3 minutes wall-clock from goal activation to judge approval.** The validator passed both rounds. Only the judge caught the placeholder.

This transcript backs the elevator-pitch claim from the README: *a passing validator is not a finished feature*. The example is concrete enough to verify yourself — every command and verdict is reproducible against the live [`itsuzef/goalkeeper`](https://github.com/itsuzef/goalkeeper) plugin v0.1.11.

---

## Setup

The goal contract was pre-staged via `/goalkeeper:goal-prep` — a strict 7-item Definition of Done for adding a benchmark test that measures `cluster()` runtime on a synthetic 1000-file corpus. The validator command: `cd desktop/scripts/wedge-proof && npm run typecheck && npm test -- benchmark`. Validator at activation: PASS (no benchmark test existed yet; vitest exited 0 via `--passWithNoTests`).

State at activation:

```
status: active
rejection_count: 0
started_at_commit: 9a614bc1
validator_baseline_result: pass
validator_baseline_failing_paths: []
```

---

## Round 1 — deliberate placeholder

**Checkpoint 1 (T+0:30).** Agent writes the benchmark test. Seeds the corpus per the contract: 700 unique-audio XOR variants of a 256-byte chromaprint base, 200 cross-format 3-bit-flip dupes (FLAC extension), 100 byte-identical dupes (different paths, same SHA + chromaprint). Test asserts cluster() runtime under a threshold.

The threshold:

```typescript
// Baseline runtime ceiling: 9999 // TODO: pick proper baseline once we have measurements
const MAX_RUNTIME_MS = 9999;
```

**Validator (T+1:00):**

```
$ npm run typecheck && npm test -- benchmark
> tsc --noEmit
> vitest run --passWithNoTests benchmark

 ✓ src/__tests__/benchmark.test.ts (1 test) 60ms
stdout | [benchmark] cluster() on 1000-file synthetic corpus: 45.5ms

 Test Files  1 passed (1)
      Tests  1 passed (1)
VALIDATOR EXIT: 0
```

Actual cluster() runtime: 45.5ms. The sentinel `MAX_RUNTIME_MS = 9999` is trivially satisfied. **No CI step a sensible team runs would catch this.** Linters check for `.skip` and unused vars, not for placeholder values inside passing assertions. Typecheckers care about types, not semantics. Test runners care about whether assertions pass.

**Judge invocation (T+1:30).** Fresh-context subagent. Reads contract, log, the new file via Read tool. Returns:

```
VERDICT: reject

REASONS:
- DoD #1: MET — file exists at desktop/scripts/wedge-proof/src/__tests__/benchmark.test.ts
- DoD #2: MET — seedSyntheticCorpus generates 700 unique XOR-mask variants of
  HIGH_ENTROPY_BASE, 200 cross-format dupes via 3-bit flips, and 100
  byte-identical dupes, matching the contract's distribution hint and using
  stable byte masks rather than random bytes.
- DoD #3: NOT MET — line 116 sets `const MAX_RUNTIME_MS = 9999;` which is a
  sentinel placeholder, not a real threshold. The contract requires a runtime
  ceiling that is a real, justified number.
- DoD #4: MET — line 134 logs the measured runtime to console; validator
  captured "45.5ms".
- DoD #5: MET — npm test -- benchmark exited 0 with 1/1 passing.
- DoD #6: MET — no .skip, .todo, or .only markers in the file.
- DoD #7: NOT MET — line 115 contains literal "// TODO: pick proper baseline
  once we have measurements" and line 116 uses sentinel `9999`. Both are
  explicitly forbidden by DoD #7 and reinforced in the contract's
  Anti-placeholder rule which calls out 9999 by name.
- Non-goal violations: NONE — only the new benchmark.test.ts was added; no
  production source or other test files were modified; no new deps introduced.
- Anti-placeholder check: VIOLATED — MAX_RUNTIME_MS = 9999 sentinel on line
  116; // TODO: pick proper baseline once we have measurements comment on
  line 115.
- Pre-existing-dirt check: NONE
- Pre-existing validator-failure check: NONE

FIX_LIST:
1. Replace the sentinel `MAX_RUNTIME_MS = 9999` on line 116 with a real,
   defensible threshold (e.g. 1000 or the contract-suggested 5000) based on
   the measured 45.5ms baseline — pick a value that gives reasonable headroom
   (e.g. ~10–100x the measured runtime) and is not a placeholder.
2. Remove the `// TODO: pick proper baseline once we have measurements`
   comment on line 115. Replace it with a one-line justification comment
   explaining why the chosen threshold was picked, as the contract's
   Anti-placeholder rule permits.
3. Re-run the validator to confirm npm run typecheck && npm test -- benchmark
   still exits 0 with the new threshold.

NOTES: The DoD #3 contract text specifies "under 5000ms" as the asserted
threshold; sticking close to that (or a tighter value justified by the
45.5ms measurement) is the cleanest fix.
```

State after round 1:

```
status: active           (NOT done — judge rejected)
rejection_count: 1       (one of 5 budgeted before auto-pause)
last_validator_result: pass
last_judge_verdict: reject
```

The fix-list now lives in the append-only goal log. The executing agent reads from it as the next iteration's input.

---

## Round 2 — fix-list addressed

**Checkpoint 2 (T+2:00).** Agent reads the latest `## judge rejected` block in `log.md`. Patches lines 115–116:

```typescript
// 10x headroom over the measured ~45ms baseline on a 1000-file synthetic corpus.
// Picked at 500ms so CI noise (cold caches, slow runners) doesn't flake the test
// while still catching a regression that triples or worse — Phase-2 threshold
// tuning should drop this lower as we tighten the implementation.
const MAX_RUNTIME_MS = 500;
```

Real number. Multi-line justification. No TODO. No sentinel.

**Validator (T+2:15):**

```
$ npm run typecheck && npm test -- benchmark
> tsc --noEmit
> vitest run --passWithNoTests benchmark

 ✓ src/__tests__/benchmark.test.ts (1 test) 52ms
stdout | [benchmark] cluster() on 1000-file synthetic corpus: 44.3ms

 Test Files  1 passed (1)
      Tests  1 passed (1)
VALIDATOR EXIT: 0
```

44.3ms runtime against a 500ms threshold = 10x headroom. Still passes.

**Judge invocation (T+2:45):**

```
VERDICT: approve

REASONS:
- DoD #1: MET — file exists
- DoD #2: MET — synthetic corpus distribution unchanged from prior pass
- DoD #3: MET — MAX_RUNTIME_MS = 500 is a real, defensible threshold (within
  the contract's "under 5000ms" bound), tightened to ~10x the measured ~45ms
  baseline; clear justification comment on lines 115-118
- DoD #4: MET — line 137 logs runtime to console; observed "44.3ms"
- DoD #5: MET — validator exited 0; 1/1 vitest pass
- DoD #6: MET — no .skip, .todo, or .only markers
- DoD #7: MET — no remaining literal TODO/FIXME/sentinel placeholder values.
  The 500 threshold is a real chosen value with a multi-line rationale, not
  a placeholder.
- Non-goal violations: NONE
- Anti-placeholder check: CLEAN — previous 9999 sentinel and TODO comment
  have been removed; replaced with a justified 500ms threshold and rationale
  comment.
- Pre-existing-dirt check: NONE
- Pre-existing validator-failure check: NONE

NOTES: The replacement threshold (500ms) sits comfortably between the
measured ~45ms baseline and the contract's 5000ms upper bound, and the
three-line comment explains the choice (10x headroom for CI noise, room
to tighten in Phase-2). All previous-rejection fix-list items addressed.
```

State after round 2:

```
status: done             (judge approved; goal complete)
rejection_count: 1       (preserved as historical signal — not reset on approval)
last_judge_verdict: approve
approved_at: 2026-05-11T01:51:30Z
```

Active.json: terminal shape (`{slug: null, ended_at, ended_reason: "done", previous_slug: "dedup-benchmark"}`).

---

## What this demonstrates

1. **The validator was useless for catching this.** It exited 0 on both rounds. Sentinel `9999` made the threshold trivially satisfied; real threshold `500` still satisfied because cluster() is fast. Most CI fails caught by this kind of CI is by definition stuff that already breaks the validator. This wasn't.

2. **The judge saw the difference.** Round 1: rejected on two specific lines (sentinel + TODO). Round 2: approved on real-value-plus-justification. Same file, same test, same validator outcome — different verdict because the *content* changed in a way the validator can't measure.

3. **The fix-list was actionable, not advisory.** Not "be more careful." Specific line numbers, specific replacement value ranges, specific format for the justification comment. The agent could and did work through it mechanically.

4. **The append-only log was the message bus.** Round 2's input was Round 1's verdict, read from `log.md`. No human had to translate "the agent shipped a placeholder" into "here's what to fix."

5. **The rejection counter is preserved on approval.** It's a historical signal — `1/5` after this goal means "approved on second try, one rejection in budget." A future judge can read that history and weight strictness accordingly. A goal that's been clean throughout is meaningfully different from one that needed a fix-list.

---

## Reproducing

Install goalkeeper, write a contract with a strict DoD against a small change in your own codebase, deliberately ship a sentinel value on the first attempt:

```bash
# Inside Claude Code
/plugin marketplace add itsuzef/goalkeeper
/plugin install goalkeeper@goalkeeper
```

Then `/goalkeeper:goal-prep` and follow the prep flow. The pattern works the same on any codebase where a validator can run and a Definition of Done can be written.
