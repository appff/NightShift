# Features

This document lists Night Shift features and where they are configured.

## Orchestration

- Sequential or parallel task execution.
- Optional planner to expand goals into task lists.
- Resume after interruption (default enabled).

## Cognitive Architecture (New in v5.0) 🧠

Night Shift now incorporates "SuperClaude" inspired cognitive modules for evidence-based autonomy.

### 1. Reflexion Memory (`nightshift/memory.py`)
- **What**: A structured, long-term memory system that stores **Error → Root Cause → Fix** patterns.
- **Why**: Prevents Hassan from repeating the same mistakes across different sessions.
- **How**: Before executing, the Brain checks `reflexion.jsonl` for similar past errors and injects proven solutions directly into the context.

### 2. Context-Oriented Personas (`nightshift/context.py`)
- **What**: Move persona definitions from `settings.yaml` to rich Markdown files in `personas/*.md`.
- **Why**: Allows for complex behavioral guidelines, "Boundaries" (DO NOTs), and specific focus areas.
- **How**: The Context Loader injects the selected persona (e.g., `architect.md`) into the system prompt dynamically.

### 3. Confidence Check (Pre-Flight) (`nightshift/validation.py`)
- **What**: A "Go/No-Go" gauge before starting a task.
- **Why**: Prevents "running blind" and wasting tokens on impossible tasks.
- **How**: Checks for documentation existence, potential duplication, and task clarity. If confidence < 0.7, it warns the user or suggests deep research.

### 4. Self-Check Protocol (Post-Flight) (`nightshift/validation.py`)
- **What**: A mandatory quality gate before reporting "Mission Completed".
- **Why**: Prevents hallucinated success ("I fixed it" without running code).
- **How**: Enforces "The 4 Questions":
    1. Are all tests passing? (Evidence required)
    2. Are requirements met?
    3. Are assumptions verified?
    4. Is there evidence (diffs/logs)?

### 5. Token Optimization (`nightshift/optimizer.py`)
- **What**: Smart context loading strategies for large projects.
- **Why**: Sending the entire codebase to the LLM is slow and expensive.
- **How**:
    - **Layer 0 Bootstrap**: Initially loads only the file tree and README.
    - **Progressive Loading**: Selectively reads file contents based on task intent.

## Agents

- **Brain**: Structured CLI LLM command generator.
  - **Structured Reasoning**: Outputs JSON for unambiguous command and status tracking.
  - **Scope Enforcement**: Prevents task creep.
- **Hassan**: CLI LLM executor (Claude, Codex, Gemini).
  - **Tail-based Filtering**: Automatically strips execution noise.
- **Critic**: Optional QA gate with multi-critic voting.

## Safety

- Auto rollback on failure.
- Backup branch creation.
- Worktree preview before applying changes.
- Approval gate for destructive commands.

## Observability

- Structured logs and history files.
- Summary JSON for each run.
- **Reflexion Logs**: `.night_shift/reflexion.jsonl` stores learned patterns.

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