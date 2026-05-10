# Changelog

All notable changes to **goalkeeper** are documented here.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-05-10

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
