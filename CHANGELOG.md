# Changelog

All notable changes to **goalkeeper** are documented here.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.11] - 2026-05-11

Tiny fix surfaced while staging a goalkeeper demo on a separate repo
(idbro). `scripts/validate-contracts.py` crashed with `ValueError: ... is
not in the subpath of ...` when given an explicit path argument pointing
at a contract outside the goalkeeper repo.

### Fixed

- `scripts/validate-contracts.py` — falls back to the absolute path when
  a target file is outside `REPO_ROOT` instead of crashing. Repo-internal
  files still display as relative paths (tidy output). Lets the script
  validate contracts in other repos when called with explicit CLI args:
  `python3 scripts/validate-contracts.py /other/repo/.claude/goals/foo/contract.md`.

## [0.1.10] - 2026-05-10

Pre-launch branding pass. No skill behavior or spec changes — purely
README hero polish and ship-ready brand assets.

### Added

- `branding/mark.svg` — icon mark (64×64). Three vertical goal-posts
  topped by a crossbar; reads as both soccer goal and judicial gate.
- `branding/wordmark.svg` — lowercase monospace wordmark (480×96).
- `branding/lockup.svg` — mark + wordmark (640×96). The "logo proper."
- `branding/social-card.svg` — 1200×630 OG image for Twitter / Slack /
  Discord link unfurls. Tagline: "Set durable goals. Approve at the gate."
- `branding/README.md` — usage notes, color palette, typography stack,
  SVG→PNG conversion recipes, and don't-do list.
- README "Brand" section linking to the brand kit.
- README footer mark.

### Changed

- README hero rewritten:
  - Lockup image above the fold
  - Tagline as h3 subtitle: "Set durable goals. Approve at the gate."
  - Badge row: test (CI), license, version, claude-code-plugin
  - **Comparison table** showing goalkeeper vs OpenAI Codex `/goal` vs
    Ralph loop across 9 dimensions (durable goals, validator, judge
    gate, anti-placeholder, chains, auto-pause, append-only log, spec
    location, validator-baseline subtraction). The judge column is the
    elevator pitch.
  - "Inspired by..." moved below the comparison so the differentiation
    is visible first.
- README link to canonical state shapes updated from `skills/goal.md`
  to `skills/goal/SKILL.md` (path fix after the v0.1.6 layout change).

### Brand kit

- **Primary color:** `#0E7C66` (deep teal-emerald)
- **Typography (wordmark):** monospace stack — `ui-monospace,
  'JetBrains Mono', 'SF Mono', Menlo, Consolas`
- **Typography (headlines):** system sans
- **Tagline:** "Set durable goals. Approve at the gate."

Drafts and alternate concepts live in
`~/Documents/context-relay/projects/goalkeeper/branding/` (not in
this repo per the hybrid branding-placement decision).



Spec extension driven by the v2-shadow-pipeline dogfood on the
agently-ai codebase: the contract's validator was `npm run test &&
npm run test:e2e && npm run lint`, and lint was already failing at
the baseline commit on two files the goal never touched. Every
checkpoint's validator run would have failed for reasons unrelated
to the goal's work, polluting the judge's verdict. v0.1.9 adds the
mechanism to detect and subtract this pre-existing debt.

### Added

- `state.json` schema (canonical, in `skills/goal/SKILL.md`) gained two
  optional fields:
  - `validator_baseline_result`: `"pass" | "fail" | "not_runnable" | null`
  - `validator_baseline_failing_paths`: array of paths the validator
    was already failing on at activation

### Changed

- `skills/goal-prep/SKILL.md` — when prep runs the validator once to
  confirm it executes, it now also captures the exit code AND the list
  of failing file paths from the output. Both flow into the activation
  state.json so the judge can subtract pre-existing failures.
- `skills/goal/SKILL.md` — activation step 3 picks up the
  validator baseline from prep (when present) and writes it into
  state.json alongside the existing `started_at_commit` /
  `started_at_dirty_paths`.
- `skills/goal-judge/SKILL.md` — Inputs section names the two new
  state fields. "Pre-existing-dirt subtraction" gained a sibling
  section ("Pre-existing validator-failure subtraction") spelling out:
  - Goal-caused failure: validator passed at baseline but fails now,
    OR fails on a path the goal modified that wasn't in
    `validator_baseline_failing_paths`. Blocks approval.
  - Pre-existing failure: validator was already failing on a path the
    goal didn't modify. Does NOT block approval; surface in NOTES.
- `skills/goal-judge/SKILL.md` — subagent prompt template now
  includes the validator baseline + pre-existing-failing-paths in the
  "Diff scope" header, plus a new "Pre-existing validator-failure
  check" line in the structured-response format.
- `README.md` — "State and storage" section documents the two new
  optional state fields.

### Why this matters

Without this mechanism: any contract whose validator chains multiple
commands (`test && lint && typecheck && ...`) is at the mercy of every
unrelated failure in the codebase. The judge would reject every
checkpoint until the entire repo is clean, which makes goalkeeper
unusable on real codebases with pre-existing debt.

With this mechanism: the goal proceeds. The judge correctly
distinguishes "this goal broke X" from "X was already broken." The
user can opportunistically fix the pre-existing debt or amend the
contract to scope the validator to changed files — informed by the
judge's NOTES section.

### Verified

- **Local install end-to-end on developer machine 2026-05-10:**
  `claude plugin validate .` passes; `claude plugin marketplace add
  ~/Documents/goalkeeper` succeeds; `claude plugin install
  goalkeeper@goalkeeper` produces v0.1.8 install at
  `~/.claude/plugins/cache/goalkeeper/goalkeeper/0.1.8/` with all 7
  SKILL.md files discovered and the plugin shown as `✔ enabled` in
  `claude plugin list`. Strongest possible release-readiness signal
  short of in-session skill invocation (which requires a Claude Code
  session restart).

### Added

- `scripts/test-lifecycle.py` — 10th test (`test_judge_advisory_no_state_change`)
  covering the goal-judge.md "advisory mode" invariant: when invoked
  on-demand outside the auto-gate flow, the judge does NOT modify
  state.json, rejection_count, or active.json. Closes the previously-
  noted "inline judge mode never tested" gap. Total now 59 assertions
  across 10 tests.

## [0.1.8] - 2026-05-10

### Added

- `.github/workflows/test.yml` — GitHub Actions workflow running on
  every push to main and every PR. Steps:
  1. Install pyyaml + jsonschema.
  2. Run `scripts/validate-contracts.py` (every contract conforms
     to the schema).
  3. Run `scripts/test-lifecycle.py` (54-assertion state-machine suite).
  4. JSON-lint the manifest files (plugin.json, marketplace.json,
     contract.schema.json).
  5. Verify each `skills/<name>/SKILL.md` exists with frontmatter
     declaring `name: <name>` matching the directory.

### Why

This locks in the regression protection from v0.1.4 (schema validity)
and v0.1.7 (lifecycle suite) so future contributors can't accidentally
ship a YAML-broken contract or a SKILL.md naming mismatch. The skill-
naming check would have caught the v0.1.6 layout mistake at PR time
instead of release time.



### Added

- `scripts/test-lifecycle.py` — re-runnable spec-conformance suite
  encoding 54 assertions across 9 state transitions. Closes the v0.1.5
  "deferred to v0.2" gap. Stdlib-only (no extra deps), runs in seconds,
  exits non-zero on any failure. Suitable for CI / pre-commit. Tests:
  - `/goal-pause`: active → paused
  - `/goal-resume`: paused → active
  - `/goal-clear`: active → cleared + archived
  - `/goal-resume` from needs_human with rejection counter reset
  - max_rejections threshold (4 → 5 → needs_human)
  - chain completion (cursor reaches end → chain done)
  - `/goal-clear` during active chain (chain.status flips to aborted,
    unreached link contracts preserved)
  - judge approve on standalone goal (terminal active.json)
  - judge reject below threshold (rejection_count++, stays active)
- `CONTRIBUTING.md` — added "Running the lifecycle suite" pointer.

### Notes

This is a *spec consistency* test, not a Claude Code skill integration
test — it codifies the canonical state shapes from
`skills/goal/SKILL.md` and verifies that constructing them per spec
produces the expected results. If a SKILL.md ever drifts from the
canonical shapes documented in `goal`, this test catches the
divergence on the next run.



**Plumbing release — required for `/plugin install` to work.** Verified
against installed plugins on disk (caveman, ralph-loop) before
restructure. No skill behavior changes.

### Changed

- Skills restructured from flat `skills/<name>.md` to the official
  Claude Code plugin layout `skills/<name>/SKILL.md`. All 7 skills
  moved via `git mv` to preserve history. Required because Claude
  Code discovers skills at `<plugin-root>/skills/<name>/SKILL.md`
  and ignores flat `.md` files inside `skills/`.
- `README.md` install section rewritten. The previous instructions
  (`/plugin install itsuzef/goalkeeper`) wouldn't have worked —
  Claude Code requires marketplace registration first. New flow:
  ```bash
  /plugin marketplace add itsuzef/goalkeeper
  /plugin install goalkeeper@goalkeeper
  ```
- README documents the namespace-prefix invocation pattern
  (`/goalkeeper:goal "<obj>"`) and a recommended `~/.claude/settings.json`
  alias block for users who want shorter commands.

### Added

- `.claude-plugin/marketplace.json` — required for `/plugin marketplace
  add` discovery. Lists goalkeeper as a single-plugin marketplace
  pointing at the repo root. Modeled on the structure of installed
  plugins on the developer's machine.

### Why this wasn't caught earlier

The four prior dogfood runs (chain, rejection cycle, lifecycle,
schema audit) were all manual walkthroughs of the skill *content* —
they verified that the skill markdown bodies produced correct state
transitions when followed. None of them exercised Claude Code's
*discovery* of those skills, because we were running the skills
manually rather than installing the plugin. The fifth release-readiness
gate was "compare on-disk structure to a real installed plugin," which
caught the layout divergence.



Verification release: comprehensive lifecycle dogfood (pause / resume /
resume-from-needs_human / clear / chain-abort) revealed one small spec
gap, fixed here. No skill behavior changes from a user perspective.

### Changed

- `skills/goal-clear.md` — clarified the chain-handling step:
  - The chain-level log entry on abort goes to the cleared slug's
    own `log.md` (chain-level events are reconstructible from
    per-link logs + chain.json; no separate chain-log file).
  - Explicitly addressed the `chain.json.status` already-`done`/-`aborted`
    case: leave chain.json untouched (you're archiving a goal whose
    chain finished earlier, not aborting in-flight).
  - Reaffirmed: unreached chain-link contracts stay in place for
    re-use.
  - Spelled out the `cleared` (per-goal) vs `aborted` (chain-level)
    distinction so the two terminal flags don't get conflated.

### Verified by dogfood

Lifecycle dogfood ran every state transition with synthetic fixtures
and hand-authored Python assertions:

- **/goal-pause**: active → paused (7 assertions PASS).
- **/goal-resume from paused**: paused → active (5 assertions PASS).
- **/goal-clear**: active → cleared with archive flow (10 assertions
  PASS — directory moved not deleted, all state files preserved,
  active.json terminal shape correct).
- **/goal-resume from needs_human with counter reset**: needs_human →
  active, rejection_count 5 → 0, audit-trail timestamps preserved (7
  assertions PASS).
- **/goal-clear during active chain**: active → cleared, chain.status
  flipped to aborted, link 1 archived, unreached link 2 contract
  preserved (11 assertions PASS — including the critical distinction
  that active.json `ended_reason="cleared"` while chain.json
  `status="aborted"`).
- **max_rejections threshold**: synthetic test with rejection_count=4
  → simulated 5th reject → status flipped to needs_human, log
  captured paused entry, active.json correctly stayed in active
  shape (7 assertions PASS).

Total: 47 lifecycle assertions across 6 transition paths, all PASS.

### Known coverage gaps (deferred)

- 3 alternate user-choice paths in `/goal-resume` from needs_human:
  Continue without reset, Abandon-via-resume.
- `/goal-pause` when already paused (should no-op per spec).
- `/goal-clear` when no active goal (should tell user and stop).
- `/goal-resume` from `done` state (should refuse per spec).

Each is a mechanical no-op or refusal path. v0.2 may add a
`scripts/test-lifecycle.py` covering all transitions automatically.



Driven by a schema-validity audit run during the rejection-cycle dogfood.
Every contract in the repo now validates against `contract.schema.json`,
and there's a script for users to run the same check locally.

### Added

- `scripts/validate-contracts.py` — walks the repo, finds every
  `*.md` with frontmatter declaring a `slug`, and validates it against
  `schemas/contract.schema.json` (using `pyyaml` and `jsonschema`).
  Skips files without a `slug` field (chain files, skill files,
  README, etc.) unless `--strict` is passed. Exits non-zero on any
  validation failure, suitable for CI / pre-commit.
- `CONTRIBUTING.md` — new "YAML pitfalls" subsection in "Writing a
  contract" calling out the two patterns that broke contracts in the
  audit: bullets starting with a quoted phrase, and unquoted strings
  containing colons inside quoted phrases. Both are caught by
  `validate-contracts.py`.

### Fixed

- `examples/migration.md` — DoD bullet that started with `"pnpm
  test"` (broke YAML parsing because the bullet's value was a
  quoted scalar followed by unparseable trailing text). Rewritten as
  `The "pnpm test" command runs ...`. Discovered when running the
  new `validate-contracts.py` against the repo.



Spec-tightening release driven by findings from the rejection-cycle
dogfood (one natural reject-then-fix-then-approve cycle on a
contributing-md goal, plus a synthetic max_rejections threshold test).

### Added

- `skills/goal.md` — `needs_human_at` timestamp added to the canonical
  state.json schema, parallel to `approved_at` / `paused_at` /
  `resumed_at`. Populated when `rejection_count` reaches
  `max_rejections` and status flips to `needs_human`.
- `CONTRIBUTING.md` — first contributor guide. Sections cover
  adding a skill, writing a contract, and running a dogfood loop
  with a concrete worked-example session. Produced by the
  rejection-cycle dogfood (rejected on first pass for a placeholder,
  approved on second pass after the fix-list was addressed).

### Changed

- `skills/goal-judge.md` — subagent prompt template gained an
  explicit "Output the verdict ONCE. Pre-think your reasoning before
  producing the structured response. Do not self-correct or revise
  individual DoD lines mid-response" instruction. Removes the
  in-response self-correction observed during the first reject-cycle
  judgment (judge marked one DoD NOT MET then corrected to MET inside
  the same verdict).
- `skills/goal-judge.md` — `On reject` threshold-check step now
  explicitly sets `state.needs_human_at` and clarifies that
  `active.json` is NOT touched on `needs_human` (the goal is paused
  awaiting human input, not terminated).

### Verified by dogfood

- Validator-vs-judge separation works as designed: a validator-
  passing file does not mean a judge-approving file. The contributing-
  md goal had a loose validator (file existence + section headers)
  and a strict DoD (no placeholders, concrete examples). First pass
  passed validator and was rejected by the judge; second pass passed
  both.
- Judge correctly distinguishes literal placeholders from rule-
  documentation references (e.g. "avoid 'TODO: real implementation'
  patterns" is rule discussion, not a violation).
- Fix-list flow works: executing agent reads the latest "judge
  rejected" block from log.md and addresses each item before re-
  judging. log.md is functional as the message bus between
  iterations.
- max_rejections threshold logic is correct: synthetic test with
  rejection_count=4 → simulated 5th reject → state.status correctly
  flipped to `needs_human`, log captured the paused entry, active.json
  correctly stayed in active shape.



Spec-tightening release driven by findings from the second dogfood run
(`/goal-chain` end-to-end on the goalkeeper repo itself, 2 links, both
judge-approved).

### Changed

- `skills/goal.md` — added a "Canonical state shapes" section as the
  single source of truth for `active.json`, `<slug>/state.json`, and
  `chain.json` schemas. Other skills now reference this section instead
  of inlining their own divergent shapes.
- `active.json` schema converged on two shapes only: **active**
  (`{slug, activated_at, chain?}`) or **terminal**
  (`{slug: null, ended_at, ended_reason, previous_slug?, previous_chain?}`).
  Previously each terminal flow (done, cleared, chain_completed) wrote
  a different ad-hoc shape.
- `skills/goal-clear.md` — clear flow writes the canonical terminal
  shape with `ended_reason: "cleared"`. When clearing during a chain,
  also includes `previous_chain`; the chain.json carries the abort
  signal separately.
- `skills/goal-judge.md` — on-approve standalone path writes the
  canonical terminal shape with `ended_reason: "done"`.
- `skills/goal-judge.md` — replaced the prose "Compute the diff
  scope" section with a 5-step mechanical assembly procedure
  containing exact shell command templates (`git diff
  <baseline>..HEAD`, `git ls-files --others --exclude-standard`, etc.)
  and a copy-pasteable `DEFAULT_EXCLUDES` array. Removes inconsistency
  risk between judge invocations.
- `skills/goal-chain.md` — chain-completion path writes the canonical
  terminal shape with `ended_reason: "chain_completed"` plus
  `previous_chain` and `previous_slug`.
- `skills/goal-chain.md` — chain advance now documents an atomic write
  order (mark previous done → record link approval → increment cursor
  → initialize next state.json + log.md → update active.json LAST) so
  interruptions leave a recoverable state.
- `skills/goal-chain.md` — status-mode print format now includes
  per-link approval timestamps from `chain.json.link_approvals[]`,
  plus chain-level started_at / completed_at lines.

### Added

- `chain.json` schema gained `link_approvals: [{slug, approved_at}]`.
  Initialized empty by `/goal-chain` start; the goal-judge skill
  appends one entry per approved chain link before handing off to
  goal-chain advance. Provides chain-level visibility without having
  to walk per-link `state.json` files.
- `skills/goal-chain.md` — new "Recovery from interrupted advance"
  section documenting four symptoms of a half-failed advance (cursor
  advanced but active.json stale; cursor advanced but next state.json
  missing; previous done but cursor not advanced; missing
  link_approvals entry) and the corresponding manual recovery for
  each.
- `README.md` — "State and storage" section now documents the
  canonical shapes for `active.json`, `state.json`, and `chain.json`
  with cross-reference to `skills/goal.md` as the source of truth.

### Fixed

- The three previously-divergent terminal `active.json` shapes
  (`{slug: null, completed_at}`, `{slug: null, cleared_at}`,
  `{slug: null, chain_completed_at}`) are now unified, eliminating a
  class of cross-skill bugs where one skill wrote a shape another
  skill couldn't read.



### Changed

- `skills/goal-judge.md` — judge subagent prompt now instructs the agent to
  Read each modified or added file end-to-end via the Read tool, not just
  trust the diff. Diffs lose context (renames, surrounding code, file-level
  structure) and were letting placeholder patterns slip through during the
  first dogfood run.
- `skills/goal-judge.md` — judge now applies a default exclusion list
  (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`,
  `poetry.lock`, `go.sum`, `Gemfile.lock`, `composer.lock`, `dist/`,
  `build/`, `out/`, `target/`, `.next/`, `*.min.js`, `*.min.css`,
  `coverage/`, `.nyc_output/`, `test-results/`, `.vscode/`, `.idea/`,
  `.DS_Store`) so auto-generated noise stays out of the judge's context.
- `skills/goal-judge.md` — judge verdict format extended with an
  explicit `Pre-existing-dirt check` line so changes to paths that
  were already dirty at activation are flagged for review rather than
  silently credited as goal work.

### Added

- `skills/goal.md` — goal activation now captures `git rev-parse HEAD`
  and `git status --porcelain` into `state.started_at_commit` and
  `state.started_at_dirty_paths`. The judge uses these as the diff
  origin and pre-existing-dirt baseline.
- `schemas/contract.schema.json` — optional `diff_excludes: string[]`
  field for per-repo noise globs that should be excluded from the
  judge's diff in addition to the defaults.
- `README.md` — documents the new `diff_excludes` contract field and
  the `started_at_commit` state field.

## [0.1.0] - 2026-05-10

### Added

- Initial public release of the **goalkeeper** Claude Code plugin.
- Plugin manifest at `.claude-plugin/plugin.json`.
- Skill: `/goal "<objective>"` — set or check status of a durable
  contract-driven goal. Auto-routes to `/goal-prep` when no contract
  exists for the slug.
- Skill: `/goal-prep "<rough idea>"` — interactive contract drafter.
  Surveys the repo and uses targeted questions to lock in objective,
  Definition of Done, validator command, and non-goals before
  execution begins.
- Skill: `/goal-pause` — pause an active goal without losing state.
- Skill: `/goal-resume` — resume a paused or `needs_human` goal,
  with explicit confirmation before resetting the rejection counter.
- Skill: `/goal-clear` — stop and archive the active goal to
  `.claude/goals/_archive/`. Files are moved, never deleted.
- Skill: `/goal-judge` — the gate. Default subagent mode spawns a
  fresh-context agent that reviews the diff and progress log against
  the contract's Definition of Done and returns approve / reject
  with a structured fix-list. Inline mode is available for cheap
  advisory iteration but not for chain gating.
- Skill: `/goal-chain "<file>"` — run a linear sequence of goals
  with judge-gated progression between them. The judge approves
  each link before the next starts.
- Contract schema at `schemas/contract.schema.json` (JSON Schema
  draft 2020-12) covering objective, non_goals, definition_of_done,
  validator, checkpoint_cadence, max_rejections, judge_mode,
  wakeup_seconds.
- Three example contracts under `examples/`: a Jest-to-Vitest
  migration, an iterative prompt-optimization run, and a four-step
  chain.
- `README.md` covering install, quick start, command reference,
  contract format, chain definition, state-and-storage layout, and
  design notes.
- MIT `LICENSE`.
- Anti-placeholder rule borrowed from the Ralph loop: stubs, mocks,
  `.todo`, `.skip`, and "TODO: real implementation" patterns are
  automatic judge rejection regardless of validator status.
- Cache-aware wakeup-delay guidance (60-270s for tight loops,
  1200-1800s for slow validators or idle waits, avoid 300s) so
  autonomous loops don't burn the Anthropic prompt cache TTL.

[Unreleased]: https://github.com/itsuzef/goalkeeper/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/itsuzef/goalkeeper/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/itsuzef/goalkeeper/releases/tag/v0.1.0
