# goalkeeper

Durable, contract-driven goal execution for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). Set a goal once, walk away, come back to a finished task — or a clear list of why it isn't done yet.

Inspired by [OpenAI Codex `/goal`](https://developers.openai.com/codex/use-cases/follow-goals) and Geoffrey Huntley's [Ralph loop](https://ghuntley.com/ralph/), with one key addition: a **subagent judge** that gates completion against an explicit Definition of Done.

## Why

Codex `/goal` runs autonomously until a stop-condition is met. The Ralph loop runs `while :; do cat PROMPT.md | claude-code; done` and leans on validators (compile, test, lint) to back-pressure the model. Both work, but both have the same failure mode: **a passing validator is not the same as a finished feature**. Tests can pass on stubs. Linters can pass on `.todo`s. Codex can declare victory the moment its stop-condition string matches.

goalkeeper adds a second gate. After your validator passes, a fresh subagent — independent context, no rationalizations from the executing agent — reviews the diff and the progress log against your written Definition of Done, and either approves or returns a structured fix-list. After 5 rejections it pauses and asks for human help.

## Install

Add the goalkeeper marketplace, then install the plugin:

```bash
# inside Claude Code
/plugin marketplace add itsuzef/goalkeeper
/plugin install goalkeeper@goalkeeper
```

Skills become available under the `goalkeeper:` namespace. Invoke as `/goalkeeper:goal "<objective>"`, `/goalkeeper:goal-prep`, `/goalkeeper:goal-judge`, etc. (Most users alias the namespace away — see "Aliasing" below.)

### Aliasing the namespace

If you primarily use goalkeeper and want shorter commands, add aliases to `~/.claude/settings.json`:

```json
{
  "aliases": {
    "/goal": "/goalkeeper:goal",
    "/goal-prep": "/goalkeeper:goal-prep",
    "/goal-pause": "/goalkeeper:goal-pause",
    "/goal-resume": "/goalkeeper:goal-resume",
    "/goal-clear": "/goalkeeper:goal-clear",
    "/goal-judge": "/goalkeeper:goal-judge",
    "/goal-chain": "/goalkeeper:goal-chain"
  }
}
```

## Quick start

```
/goal-prep "Migrate the test suite from Jest to Vitest"
```

goalkeeper reads your repo, asks a few targeted questions (objective, definition-of-done, validator command, non-goals), writes `.claude/goals/<slug>/contract.md`, and offers to start. Once running, it:

1. Works in checkpoints (logged to `log.md`).
2. Runs your validator after each checkpoint.
3. When the validator passes, spawns a subagent **judge** to check Definition of Done.
4. Judge approves → done. Judge rejects → fix-list logged, work continues. After 5 rejections → paused for you.

Check status anytime:

```
/goal
```

## Commands

| Command | What it does |
|---|---|
| `/goal "<objective>"` | Start (or resume) a goal. Auto-routes to `/goal-prep` if no contract exists yet. |
| `/goal` | Show status of the active goal: last checkpoint, validator state, rejection count. |
| `/goal-prep "<rough idea>"` | Interactively draft a contract — the highest-leverage step. Surveys the repo and uses targeted questions to lock in a precise spec. |
| `/goal-pause` | Pause without losing state. Pending wakeups become no-ops. |
| `/goal-resume` | Resume a paused goal. If resuming from `needs_human`, asks whether to reset the rejection counter. |
| `/goal-clear` | Stop and archive the goal to `.claude/goals/_archive/`. Files are moved, never deleted. |
| `/goal-judge` | Run the judge advisorily on the active goal (no state change). Useful as a manual sanity check. |
| `/goal-chain "<file>"` | Run a linear sequence of goals; the judge gates progression between them. |

## Contract format

A contract is a markdown file at `.claude/goals/<slug>/contract.md` with frontmatter:

```yaml
---
slug: jest-to-vitest-migration
objective: Migrate the test suite from Jest to Vitest with no behavioral regressions and a measurable speed improvement.
non_goals:
  - Do not rewrite test logic
  - Do not change source code under src/
definition_of_done:
  - All test files import from "vitest" instead of "@jest/globals"
  - jest.config.* is removed; vitest.config.ts exists with equivalent coverage thresholds
  - "pnpm test" runs the full suite under Vitest with 100% of previously-passing tests still passing
  - Wall-clock test runtime improves by at least 20% vs the Jest baseline
validator:
  command: pnpm test --run && pnpm exec node scripts/check-no-jest-refs.mjs
  success: exit_zero
  timeout_seconds: 1200
checkpoint_cadence: every 5 file edits OR every 20 minutes
max_rejections: 5
judge_mode: subagent
wakeup_seconds: 270
---

## Context
<freeform body — file pointers, constraints, hints, anti-placeholder reminders>
```

The body of the contract is your "PROMPT.md" — file pointers, constraints, hints. See [`examples/`](./examples/) for full contracts.

Schema: [`schemas/contract.schema.json`](./schemas/contract.schema.json).

### Field reference

- **slug** — kebab-case directory name. Must be unique within `.claude/goals/`.
- **objective** — one sentence, what success looks like.
- **non_goals** — explicit out-of-scope items. Judge rejects on violation even if DoD is met.
- **definition_of_done** — what the judge grades against. Be specific; "works correctly" is not a DoD.
- **validator.command** — runs after each checkpoint. Necessary but not sufficient.
- **validator.success** — `exit_zero` (default) or `regex:<pattern>` matched against stdout.
- **checkpoint_cadence** — agent's guidance for how often to log + validate.
- **max_rejections** — default 5. After this many judge rejections, pauses for human.
- **judge_mode** — `subagent` (default, gate-quality) or `inline` (cheap, advisory only).
- **wakeup_seconds** — between-iteration delay. Tune to validator runtime; goalkeeper picks cache-aware default if unset.
- **diff_excludes** — additional pathspec globs the judge should ignore. Appended to defaults (lockfiles, `dist/`, `build/`, `coverage/`, IDE files). Add per-repo noise like generated migrations or vendor trees.

## Chains

A chain is an ordered list of slugs. The judge gates progression — only after approval does the next goal start.

```markdown
---
name: bonfire-bass-rust-port
---

1. port-dsp-core-to-rust
2. wire-up-ffi-shim
3. swap-cpp-for-rust-in-host
4. delete-cpp-tree
```

Run with:

```
/goal-chain ".claude/goals/chains/bonfire-bass.md"
```

Each slug must already have a contract at `.claude/goals/<slug>/contract.md`. Run `/goal-prep` for each before starting the chain.

## Multi-role goals

Most non-trivial goals span multiple roles — backend changes, UI wiring, migrations, tests, docs. Goalkeeper deliberately keeps just two agent slots (executor + judge) and stays framework-agnostic about how you spawn specialists. There are two patterns for getting role-shaped work through goalkeeper, and the right choice depends on how decoupled the roles are.

### Pattern A — chain of role-specific contracts (default)

Frame each role as its own contract with its own Definition of Done, validator, and judge. Compose them with `/goal-chain`. The judge gates progression: backend's judge has to approve before UI starts; UI's judge has to approve before migrations.

```markdown
---
name: stripe-integration
---

1. stripe-api-routes
2. stripe-db-migration
3. stripe-checkout-ui
4. stripe-e2e-tests
```

Each slug has its own `.claude/goals/<slug>/contract.md` with a focused DoD ("Stripe webhook signature verification works", "checkout component handles 3DS challenge", etc.) and a focused validator (`pnpm test packages/api`, `pnpm test packages/web`, etc.). See [`examples/chain.md`](./examples/chain.md) for a worked example.

**Choose Pattern A when:** roles are sequenceable. One role's work produces the artifacts the next role consumes. The dependency graph is linear or close to it. You want the judge to gate-keep at each role boundary so a sloppy backend can't silently corrupt the UI step.

**Tradeoff:** chains force upfront decomposition. You have to know the boundaries before you start. If the boundaries shift mid-flight, you have to clear the chain and re-plan.

### Pattern B — in-goal `specialists:` orchestration (proposed for v0.2)

For tightly-coupled cross-role work — same files, can't be sequenced — Pattern A creates artificial mid-flight pauses. Pattern B is the escape hatch: a single contract with a `specialists:` field that lists the roles available, plus role-specific system prompts. The executing agent is the orchestrator and dispatches subtasks to specialist subagents (Claude Code general-purpose agents with custom system prompts, your own `subagent_type` definitions, or MCP-based agents — goalkeeper doesn't ship specialist definitions).

```yaml
specialists:
  - role: backend
    system_prompt: "You are a senior Node.js engineer. ..."
  - role: ui
    system_prompt: "You are a senior React engineer. ..."
```

The judge still gates final approval against the unified DoD; the executing agent's log records which specialist did what.

**Status: proposed for v0.2 — not yet implemented.** The `specialists:` field is not in `schemas/contract.schema.json` yet. If you need this today, write your own orchestration in the body of the contract and have the executing agent spawn subagents using whatever Claude Code mechanism you prefer; goalkeeper observes via the log and the judge gates the result against the unified DoD.

**Choose Pattern B when:** specialists genuinely have to interleave on the same files. A frontend change requires a simultaneous backend change, both committed together, both tested together. Pattern A would create a contract that artificially pauses the work mid-flight.

**Tradeoff:** the executing agent owns coordination state, and the judge has to reason about multiple specialists' contributions in a single DoD pass. Easier bugs to hide than in chains.

### Default: prefer A unless you can articulate why A doesn't fit

If you can list the roles in dependency order and each role can complete independently before the next starts, use Pattern A. Reach for Pattern B only when the roles must touch the same code in the same edit.

## State and storage

```
.claude/goals/
  active.json                    # pointer to current slug (or terminal record)
  chain.json                     # current chain, if any
  .gitignore                     # ignores all goal dirs except shared/ (opt-in)
  <slug>/
    contract.md                  # the spec
    state.json                   # status, rejection_count, git baseline, validator/judge results
    log.md                       # append-only checkpoint + verdict log
  _archive/                      # cleared goals (moved, never deleted)
  shared/                        # opt-in committed contracts for team sharing
```

By default everything under `.claude/goals/` is gitignored. To share a contract with your team, place it under `.claude/goals/shared/<slug>/contract.md`.

### Canonical state shapes

The skills (`goal`, `goal-clear`, `goal-judge`, `goal-chain`) all read and write the same shapes. Single source of truth lives in [`skills/goal.md`](./skills/goal.md) under "Canonical state shapes"; the reference here is for users.

**`active.json`** — exactly two shapes, active or terminal:

```json
// Active
{"slug": "<slug>", "activated_at": "<ISO>", "chain": "<chain>"}  // chain is optional

// Terminal
{
  "slug": null,
  "ended_at": "<ISO>",
  "ended_reason": "done" | "cleared" | "chain_completed" | "aborted",
  "previous_slug": "<slug>",
  "previous_chain": "<chain>"
}
```

**`<slug>/state.json`** — required fields on activation: `status`, `rejection_count`, `started_at`, `started_at_commit`, `started_at_dirty_paths`. Populated as the goal runs: `chain_step`, `last_checkpoint_at`, `last_validator_result`, `last_judge_verdict`, `approved_at`, `paused_at`, `resumed_at`.

**`chain.json`** — `name`, `slugs[]`, `cursor`, `status`, `started_at`, `completed_at`, `source_file`, `link_approvals[]`. The `link_approvals` array accumulates `{slug, approved_at}` entries as each link is judge-approved, providing chain-level visibility independent of per-link state files.

## Design notes

- **The contract is the spec.** Bad contracts produce bad work. `/goal-prep` is mandatory because thin contracts are goalkeeper's #1 failure mode.
- **Judge ≠ validator.** Validators check that things work; the judge checks that the *right* things work. Validator passing is necessary but not sufficient.
- **Subagent judge is the gate.** Independent context catches the placeholders and shortcuts the executing agent rationalized away. Inline judge mode exists for cheap advisory review only — do not use it as a gate.
- **Append-only log.** Logs are forensic artifacts. Past entries are never deleted or rewritten.
- **Cache-aware wakeup delays.** Anthropic's prompt cache has a 5-minute TTL. goalkeeper picks delays that either stay warm (60–270s) or commit to long waits (1200s+) — never the worst-of-both 300s.
- **Anti-placeholder.** Borrowed verbatim from Ralph: stubs, mocks, `.todo`, `.skip`, and "TODO: real implementation" are automatic judge rejection.

## Prior art

- **OpenAI Codex `/goal`** — the durable-objective + stop-condition pattern. goalkeeper mirrors the lifecycle (set, status, pause, resume, clear) and adds prep, judge, and chain. ([docs](https://developers.openai.com/codex/use-cases/follow-goals))
- **Ralph (Geoffrey Huntley)** — the embedded-validator loop. goalkeeper adopts the validator philosophy and the anti-placeholder rule, and adds an external judge. ([blog post](https://ghuntley.com/ralph/))

## License

MIT — see [LICENSE](./LICENSE).
