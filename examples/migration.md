---
slug: jest-to-vitest-migration
objective: Migrate the test suite from Jest to Vitest with no behavioral regressions and a measurable speed improvement.
non_goals:
  - Do not rewrite test logic or assertions
  - Do not change source code under src/
  - Do not change CI configuration in this goal (separate goal)
definition_of_done:
  - All test files import from "vitest" instead of "@jest/globals" or rely on Jest globals
  - jest.config.* is removed; vitest.config.ts exists with equivalent coverage thresholds
  - "pnpm test" runs the full suite under Vitest with 100% of previously-passing tests still passing
  - Wall-clock test runtime improves by at least 20% vs the Jest baseline captured in scripts/baseline-test-time.txt
  - No file under tests/ contains the substring "jest." (except in archived/ subfolders)
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

This repo is a TypeScript monorepo with ~340 test files across 6 packages. Jest is configured at the root (`jest.config.cjs`) with per-package overrides. We want to move to Vitest for speed and ESM-native execution.

## Files to know

- `jest.config.cjs` — root config, has projects[] with per-package settings
- `packages/*/jest.config.cjs` — per-package overrides, mostly setup files
- `packages/*/tests/setup.ts` — common setup with mock factories
- `scripts/baseline-test-time.txt` — captured Jest wall-clock baseline (regenerate before starting if older than 1 day)

## Constraints

- Do not assume an API exists in Vitest just because it exists in Jest. Search the Vitest docs first.
- Mock factories in setup.ts use `jest.fn()` extensively — these need `vi.fn()` replacements.
- Snapshot files under `__snapshots__/` should not be regenerated unless an actual content change is needed.
- If a test relies on Jest fake timers, port to `vi.useFakeTimers()` with the modern `{ now: ... }` API.

## Anti-placeholder rule

DO NOT skip tests, mark them `.todo`, or comment them out to make the validator pass. If a test cannot be ported, surface it in the rejection fix-list and stop. Skipped tests are an automatic judge rejection.
