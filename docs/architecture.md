# Architecture

This document explains how Night Shift is structured and how data flows through the system.

## Overview

Night Shift orchestrates three roles:
- Brain (Director): decides next actions using a CLI LLM.
- Hassan (Worker): executes commands using a CLI LLM or tool.
- Critic (QA): validates completion (optional).

The orchestrator coordinates these roles per mission task, writes logs, and manages safety features.

## Core Modules

- `nightshift/orchestrator.py`: mission runner, task loop, safety controls, and resume logic.
- `nightshift/agents.py`: Brain, Hassan, Critic, MemoryManager implementations.
- `nightshift/validation.py`: settings and mission validation.
- `nightshift/utils.py`: helpers (logging, driver extraction, auth linking, ignore patterns).
- `nightshift/constants.py`: global constants.
- `night_shift.py`: CLI entrypoint.

## Data Flow

1) Mission load:
   - `mission.yaml` is parsed and validated.
   - Mission-level overrides for `brain`, `body`, `critic` are merged into `settings.yaml`.

2) Agent initialization:
   - Brain, Hassan, and Critic are created from merged settings.
   - Optional auth linking is applied to isolated HOME directories.

3) Task loop (per task):
   - Hassan executes initial action.
   - Brain reads history and emits the next command.
   - Critic validates completion (unless disabled).
   - Resume state is updated after task completion.

4) Finalization:
   - Summary JSON, logs, and mission history are written.
   - Resume state is cleared on success.

## State and Logs

- Logs: `logs/night_shift_log_*.txt`
- History: `logs/night_shift_history_*.txt`
- Summary: `logs/night_shift_summary_*.json`
- Memories:
  - Project: `<project_path>/.night_shift/memories.md`
  - Global: `~/.night_shift/memories.md`
- Resume state: `<project_path>/.night_shift/state.json`

## Safety and Isolation

- Safety controls are defined in `settings.yaml` (rollback, worktrees, approvals).
- Optional isolated HOME directories for Brain/Critic/Hassan.
- `.night_shiftignore` excludes large directories during workspace copying.
