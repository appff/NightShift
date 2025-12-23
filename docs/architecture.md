# Architecture

This document explains how Night Shift is structured and how data flows through the system.

## Overview

Night Shift orchestrates three roles:
- **Brain (Director)**: Decides next actions using a CLI LLM.
- **Hassan (Worker)**: Executes commands using a CLI LLM or tool.
- **Critic (QA)**: Validates completion (optional).

The orchestrator coordinates these roles per mission task, writes logs, and manages safety features.

## Core Modules

- **`nightshift/orchestrator.py`**: The central nervous system. Manages the task loop, safety controls, and integrates all sub-modules.
- **`nightshift/agents.py`**: Implementation of Brain, Hassan, Critic agents.
- **`nightshift/memory.py`** (New): **Reflexion Memory** system for storing and retrieving error-fix patterns.
- **`nightshift/context.py`** (New): **Context Loader** for handling Markdown-based personas (`personas/*.md`).
- **`nightshift/validation.py`** (New): **Confidence Checker** (Pre-flight) and **Self-Check Protocol** (Post-flight).
- **`nightshift/optimizer.py`** (New): **Token Optimizer** for Layer 0 context bootstrapping.
- `nightshift/utils.py`, `constants.py`: Helpers and global configurations.

## Data Flow (Updated v5.0)

1.  **Mission Load & Init**:
    *   `mission.yaml` parsed (repo-scoped missions with task status tracking).
    *   **Context Loader** loads the specific persona (e.g., `architect.md`) from Night Shift's `personas/` directory by default.
    *   **Token Optimizer** generates "Layer 0 Context" (File Tree + README) to minimize initial tokens.

2.  **Task Execution Loop**:
    *   **Pre-Flight**: **Confidence Checker** evaluates the task. If confidence is low, it warns or suggests research.
    *   **Brain Planning**: Brain receives the task + Layer 0 Context.
        *   **Reflexion Injection**: If the Brain encounters an error, **Reflexion Memory** injects past solutions for similar errors.
    *   **Hassan Execution**: Hassan executes commands.
    *   **Structured Reasoning**: Brain outputs JSON (`{"command": "...", "status": "..."}`).

3.  **Completion & Verification**:
    *   **Post-Flight**: Before marking "Mission Completed", **Self-Check Protocol** runs.
        *   Did tests pass? Is there evidence? (The 4 Questions). See [Quality Gates](./quality_gates.md) for details.
    *   **Critic Review**: External Critic validates the work.

4.  **Finalization**:
    *   Logs and summaries written.
    *   New error-fix patterns are saved to `.night_shift/reflexion.jsonl`.

## State and Logs

- Logs: `logs/night_shift_log_*.txt`
- History: `logs/night_shift_history_*.txt`
- Summary: `logs/night_shift_summary_*.json`
- **Reflexion DB**: `.night_shift/reflexion.jsonl` (Structured error learning)
- Memories: `.night_shift/memories.md` (Legacy text memory)
- Resume state: `.night_shift/state.json`

## Safety and Isolation

- Safety controls in `settings.yaml` (rollback, worktrees, approvals).
- **Auth Stability**: Brain process inherits system `HOME` for auth tokens.
- **Validation Gates**: Confidence checks and Self-checks act as safety barriers against hallucination and "running blind".

## Agent Intelligence

### Persona System (Context-Oriented)

Night Shift uses a **"Context-Oriented Config"** approach. Instead of rigid code logic, agent behavior is defined by rich Markdown files in `personas/`.

#### How It Works (The Prompt Flow)

1.  **Selection**: The user selects a persona in `mission.yaml` (e.g., `persona: "python-expert"`), or regex rules in `settings.yaml` auto-select it based on the task description.
2.  **Loading**: `ContextLoader` reads `personas/python-expert.md`.
3.  **Injection (Brain)**: The content is injected into the **System Prompt** of the Brain.
    *   *Effect*: The Brain plans and reasons like a Python Expert (e.g., prioritizing TDD, Security).
4.  **Injection (Hassan)**: The content is written to a temporary system prompt file (`.night_shift_system_prompt.txt`) passed to Hassan's CLI driver.
    *   *Effect*: Hassan generates code and executes commands adhering to the persona's constraints and style.

This ensures that both the **Planner (Brain)** and the **Executor (Hassan)** align with the same specialized mindset throughout the task.
