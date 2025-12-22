# Features

This document lists Night Shift features and where they are configured.

## Orchestration

- Sequential or parallel task execution.
- Optional planner to expand goals into task lists.
- Resume after interruption (default enabled).

## Agents

- Brain: CLI LLM command generator.
- Hassan: CLI LLM executor (Claude, Codex, Gemini).
- Critic: optional QA gate with multi-critic voting.

## Safety

- Auto rollback on failure.
- Backup branch creation.
- Worktree preview before applying changes.
- Approval gate for destructive commands.

## Observability

- Structured logs and history files.
- Summary JSON for each run.
- Optional context reduction to minimize tokens.

## Configuration Highlights

Key settings in `settings.yaml`:

- `brain.active_driver`
- `body.active_driver`
- `critic.enabled`
- `planner.enabled`
- `qa.run_tests`
- `parallel.max_workers`
- `context_reduction.enabled`
- `resume`

Mission overrides in `mission.yaml`:
- `brain`, `body`, `critic` blocks override global settings for the run.
- `reviewer_mode: true` disables execution (review-only).
