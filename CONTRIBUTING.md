# Contributing to goalkeeper

Thanks for your interest. This guide covers the three things contributors do most often: adding a skill, writing a contract, and running a dogfood loop.

## Adding a skill

A skill is a markdown file under [`skills/`](./skills/) with YAML frontmatter and an instruction body. To add one:

1. Create `skills/<your-skill-name>.md` (kebab-case, no `.md` in the name elsewhere).
2. Frontmatter must have `name` (must match the filename minus extension) and `description` (one sentence — Claude Code uses this to decide when to invoke the skill).
3. The body is instructions to the agent that runs when `/<your-skill-name>` is invoked. Write in second person ("You are operating the X skill — ...").
4. Reference the skill from existing skills if it should be invoked from a workflow (e.g. goal-judge currently invokes goal-chain on chain-mode approve).
5. Update the README command table and `CHANGELOG.md` under `### Added`.

Example minimal skill:

```markdown
---
name: goal-log
description: Print the last N entries of the active goalkeeper goal's log.md.
---

You are operating the **goal-log** skill. Read `.claude/goals/active.json` →
`<slug>` → `<slug>/log.md`. Print the last 20 lines (or N if `args` is a number).
```

## Writing a contract

A contract is a markdown file at `.claude/goals/<slug>/contract.md` with YAML frontmatter that conforms to [`schemas/contract.schema.json`](./schemas/contract.schema.json) and a body containing context, file pointers, and constraints.

Required frontmatter fields: `slug`, `objective`, `definition_of_done`, `validator`. Recommended: `non_goals` (prevents scope drift), `max_rejections` (default 5), `judge_mode` (default `subagent`).

Concrete example for `definition_of_done`:

```yaml
definition_of_done:
  - All test files import from "vitest" instead of "@jest/globals"
  - jest.config.* is removed; vitest.config.ts exists with equivalent coverage
  - "pnpm test --run" runs the full suite and exits 0
  - Wall-clock test runtime improves by at least 20% vs the Jest baseline
```

The validator is necessary but not sufficient — the judge gates on the full DoD. Validators should be cheap structural checks; the judge handles the strict review. See [`examples/`](./examples/) for full contracts.

Run `python3 scripts/validate-contracts.py` to check every contract in the repo against the JSON Schema. Run `python3 scripts/test-lifecycle.py` to verify state-machine transitions still match the canonical shapes documented in `skills/goal/SKILL.md`. Two YAML pitfalls to avoid in DoD bullets:

- **Don't start a bullet with a quoted phrase.** YAML treats `- "command" runs ...` as a quoted scalar followed by garbage. Rewrite to put a word first: `- The "command" runs ...`.
- **Don't put unescaped colons inside unquoted strings.** YAML interprets `mocks, "TODO: real implementation"` as a key/value mapping. Wrap the whole bullet in single quotes: `- 'mocks, "TODO: real implementation"'`.

Both pitfalls are caught by `validate-contracts.py`, which is fast enough to run pre-commit.

## Running a dogfood loop

The fastest way to verify a change is real is to run goalkeeper against itself or a small repo where you can craft a tight contract. A typical loop:

1. **Prep the contract.** Run `/goal-prep "<rough idea>"`. The skill surveys the repo and asks targeted questions about objective, definition_of_done, validator command, and non-goals. It writes the contract to `.claude/goals/<slug>/contract.md`.

2. **Activate.** Run `/goal "<objective>"` — if a contract for the slug already exists, this skips prep and activates immediately, writing `.claude/goals/active.json` and initializing `.claude/goals/<slug>/state.json` with `started_at_commit` (current git HEAD) and `started_at_dirty_paths` (current `git status --porcelain`).

3. **Watch the loop.** The executing agent does work for one checkpoint's worth of progress, appends a checkpoint entry to `.claude/goals/<slug>/log.md`, runs the contract's validator command, then invokes the judge. The validator and judge are independent: validator does cheap structural checks, judge enforces the full DoD.

4. **Judge verdict.** On approve, `state.status` flips to `done` and `active.json` becomes the canonical terminal shape (`{slug: null, ended_at, ended_reason: "done", previous_slug: ...}`). On reject, the fix-list is appended to `log.md` and the next iteration addresses it. After 5 rejections, status becomes `needs_human` and execution pauses.

5. **Inspect.** Read `.claude/goals/<slug>/log.md` for the full audit trail, `state.json` for the current snapshot, and `active.json` to confirm whether anything is still running.

Concrete example session against the goalkeeper repo itself:

```
/goal-prep "Add a CHANGELOG.md to the goalkeeper repo with v0.1.0 and v0.1.1 entries"
# answer prep questions; contract written to .claude/goals/changelog/contract.md

/goal "Add a CHANGELOG.md to the goalkeeper repo with v0.1.0 and v0.1.1 entries"
# work happens; validator runs (file exists + version tags); judge reviews DoD

# /goal           — show current status
# /goal-judge     — advisory re-judge (state unchanged)
# /goal-clear     — abandon and archive (only if needed)
```

If the judge rejects on the first pass, the next iteration reads the latest `## judge rejected` block in `log.md` and addresses each fix-list item before re-running the validator+judge cycle.

## Anti-placeholder note

Contract DoD must avoid stubs, mocks, `.todo` markers, skipped tests, or "TODO: real implementation" patterns. The judge skill rejects these automatically regardless of validator status — borrowed verbatim from the Ralph loop's anti-placeholder rule. If a checkpoint genuinely cannot complete, surface it in the log and stop; do not paper over with placeholders to make the validator pass.

This rule applies to your CONTRIBUTING.md, contract bodies, and any worked examples you add to the docs. Concrete beats vague every time.
