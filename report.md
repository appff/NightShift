# Night Shift Project Report

## Overview
**Night Shift** is an **Autonomous Agent Orchestrator** designed to automate project completion through the collaborative efforts of a "Brain" (Director) and "Hassan" (Worker) AI agents. It stands out for its unique architecture that leverages **Pure CLI Tools** for integrating various AI models (such as Claude, Gemini, and Codex), eliminating the need for direct API SDKs within the Python codebase. The project emphasizes advanced agentic features for robust and efficient autonomous operations.

## Key Features (v4.4 Highlights)
*   **Pure CLI Brain:** Direct interaction with installed CLI tools (`claude`, `gemini`, `codex`) without API SDKs.
*   **Dual-Brain QA (Critic):** A separate AI persona (the Critic) cross-verifies every task, ensuring quality and driving iterative improvements.
*   **Long-Term Memory:** Stores lessons learned in `.night_shift/memories.md` to prevent recurring mistakes.
*   **Parallel Execution:** Ability to spawn multiple Hassan workers in isolated workspaces for simultaneous task completion.
*   **Safety Net:** Automatic Git checkpoints before each task with auto-rollback on failure.
*   **Dynamic Personas:** Support for various personas (e.g., Architect, Troubleshooter, Documenter) that synchronize across Brain and Hassan for consistent execution.

## Recent Developments and Changes

The project is under active development, with notable recent updates in versions 4.3.0, 4.3.1, and upcoming unreleased changes, highlighting a commitment to safety, configurability, and robust agentic behavior.

### Architectural & Core Changes
*   **Pure CLI Transition:** Complete shift to using CLI tools for AI model interaction, removing heavy LLM SDKs from `requirements.txt`. This includes a "Shadow Workspace" for HOME isolation and authentication symlinking for enhanced security and environment isolation.
*   **Resume Support:** Automatic resume functionality via `.night_shift/state.json`.
*   **Context Reduction:** Optional history trimming to optimize token usage.
*   **Logging:** Adoption of Python's standard `logging` module for better log management and dual output.

### Safety & Control Enhancements
*   **Improved Safety Defaults:** `auto_commit_and_push` is now disabled by default, and automatic rollback stashes uncommitted changes before resetting, safeguarding user work.
*   **Safety Gates:** Introduction of optional approval mechanisms for destructive actions and worktree previews before applying changes.
*   **Reviewer Mode:** A dedicated mode for non-executing analysis, allowing the Brain to provide feedback without making changes.

### Configurability & Workflow Improvements
*   **Per-Task Personas:** Missions can now define specific personas for individual tasks, and `persona_rules` can auto-select personas based on task patterns.
*   **Optional Planner:** A planner can now automatically expand mission goals into detailed task lists, with an optional approval step.
*   **Shared Tool Registry:** A common list of tools injected into Brain/Hassan prompts.
*   **QA Enforcement:** Optional test enforcement, configurable to run after each task or at mission completion.
*   **Mission Overrides:** `brain`, `body`, and `critic` configurations can now be overridden per mission.

## Dependencies
The project's external dependencies are notably minimal, primarily requiring `pyyaml` for configuration file parsing. This reinforces the architectural decision to rely on external CLI tools (like `claude`, `gemini`, `codex`) for core AI functionalities rather than integrating complex Python libraries for each model.

## Main Script (`night_shift.py`)
The `night_shift.py` script serves as the project's main entry point. It handles:
*   Argument parsing for mission files, logging directories, log levels, reviewer mode, auto-approval flags, and persona mapping.
*   Initialization and orchestration of the `NightShiftAgent` from `nightshift.orchestrator`, which embodies the core logic of the Brain and Hassan collaboration.

## Conclusion
Night Shift represents a powerful and flexible autonomous agent orchestrator. Its focus on CLI tool integration, robust safety mechanisms, and advanced agentic features like dual-brain QA and long-term memory positions it as a sophisticated solution for automating complex software engineering tasks. The ongoing development indicates a continuous effort to enhance its capabilities, safety, and user experience.
