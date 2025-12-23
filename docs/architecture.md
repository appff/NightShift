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
   - Authentication folders (e.g., `.claude`, `.anthropic`, `.gemini`) are linked to ensure CLI tools remain logged in.

3) Task loop (per task):
   - Hassan executes initial action.
   - Brain reads history and emits the next command.
   - **Structured Reasoning**: Brain is forced to output JSON (`{"command": "...", "status": "..."}`) to avoid conversational filler and ensure unambiguous state transitions.
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
- **Auth Stability**: Brain process inherits the system's `HOME` to ensure stable access to authentication tokens while maintaining project-level workspace isolation.
- `.night_shiftignore` excludes large directories during workspace copying.

## Agent Intelligence and Prompting

The reliability of the agents depends heavily on a robust prompt engineering and output processing strategy.

### Brain (Director) Prompting & Decision Logic

A key challenge was the `Brain` agent entering into conversational loops or ignoring task completion signals. Solutions include:

-   **Structured Output**: Forcing JSON output ensures the Brain acts as a logic engine rather than a chatbot.
-   **Scope Enforcement**: The prompt explicitly instructs the Brain to ignore optional expansions proposed by the worker (Hassan) once core task requirements are met.
-   **Prompt Ordering**: Core decision logic and instructions are placed at the end of the prompt to leverage "recency bias" in LLMs.

### Hassan (Worker) Output Processing

To prevent the Brain from being overwhelmed by large logs (especially from `codex` or `git diff`):

-   **Tail-based Filtering**: Only the final summary from Hassan (detected by markers like `tokens used` or `codex`) is sent to the Brain, stripping away noisy execution logs.
-   **Diff Truncation**: Large git diffs are automatically truncated to keep the context concise and focused on the high-level task status.
-   **Context Compaction**: Characters are strictly limited to prevent "Argument list too long" errors in CLI drivers.
