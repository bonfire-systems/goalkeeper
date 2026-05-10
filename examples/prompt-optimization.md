---
slug: classifier-prompt-optimization
objective: Iteratively refine the intent-classifier prompt until eval suite accuracy reaches 92% on the gold set without regression on the holdout set.
non_goals:
  - Do not modify the eval harness in evals/run.ts
  - Do not change the underlying model (stays on claude-haiku-4-5)
  - Do not add few-shot examples drawn from the gold set (test-set leakage)
definition_of_done:
  - Gold-set accuracy ≥ 0.92 (current baseline 0.81, captured in evals/baseline.json)
  - Holdout-set accuracy not regressed by more than 1pp vs baseline
  - Prompt length stays under 4000 tokens
  - All changes are in prompts/intent-classifier.md (no other source files modified)
validator:
  command: pnpm exec tsx evals/run.ts --suite=gold --suite=holdout --json > .goalkeeper/last-eval.json && pnpm exec tsx scripts/check-eval-thresholds.ts .goalkeeper/last-eval.json
  success: exit_zero
  timeout_seconds: 900
checkpoint_cadence: every 3 prompt revisions
max_rejections: 5
judge_mode: subagent
---

## Context

The intent-classifier prompt lives at `prompts/intent-classifier.md`. The eval harness loads it, runs every input from `evals/datasets/{gold,holdout}.jsonl`, and computes accuracy.

## Files to know

- `prompts/intent-classifier.md` — the only file you should edit
- `evals/datasets/gold.jsonl` — 200 labelled examples; you may READ to understand failure patterns but do not include verbatim in the prompt
- `evals/datasets/holdout.jsonl` — DO NOT READ. The judge will check git log to confirm.
- `evals/baseline.json` — accuracy snapshot from last green run
- `scripts/check-eval-thresholds.ts` — exits non-zero if gold < 0.92 or holdout regressed > 1pp

## Strategy hints

- Start by inspecting the rows in `.goalkeeper/last-eval.json` where the model was wrong on gold. Cluster by failure mode (ambiguity, edge cases, etc.) before editing the prompt.
- Prefer structural changes (output schema, decision tree) over example-stuffing.
- After each revision, run validator. If gold improved but holdout regressed, the change overfit — revert.
