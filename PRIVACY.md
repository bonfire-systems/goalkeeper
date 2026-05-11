# Privacy

**goalkeeper does not collect, transmit, or store any user data.**

The plugin is a set of [Claude Code skills](https://docs.claude.com/en/docs/claude-code/overview) that operate entirely on your local machine. Specifically:

## What goalkeeper writes to disk

- `.claude/goals/<slug>/contract.md` — the goal spec you (or `/goalkeeper:goal-prep`) authored
- `.claude/goals/<slug>/state.json` — current goal status, rejection count, git baseline references
- `.claude/goals/<slug>/log.md` — append-only checkpoint and judge-verdict log
- `.claude/goals/active.json` — pointer to the currently active goal
- `.claude/goals/chain.json` — chain state, when a chain is active
- `.claude/goals/_archive/` — cleared goals (moved, never deleted)

All of these live under your repository's `.claude/goals/` directory and are gitignored by default (the plugin creates an opt-out `.gitignore` on first activation).

## What goalkeeper reads

- The contract you wrote
- Your git history and working tree (via standard `git` commands)
- The output of your contract's `validator.command` (shell command exit codes and stdout/stderr)
- The diffs and files modified by the goal's work (so the judge subagent can review them)

## What goalkeeper does NOT do

- No telemetry. No analytics. No usage pings.
- No outbound network requests. The plugin itself never calls any remote service.
- No collection of code, prompts, contracts, or any other user content.
- No upload of state, logs, or diffs anywhere outside your local filesystem.

## What flows through Claude Code

When the executing agent or the judge subagent does its work, the inputs and outputs of that work are processed by Claude (Anthropic's models) the same as any other Claude Code interaction. That data flow is governed by **[Anthropic's Privacy Policy](https://www.anthropic.com/privacy)** and Claude Code's own privacy practices — not by goalkeeper, which is just a thin plugin layer of skill instructions.

## Questions

Open an issue at [github.com/itsuzef/goalkeeper/issues](https://github.com/itsuzef/goalkeeper/issues) or email itsuzef@gmail.com.
