# 🌙 Night Shift: The Autonomous Overlord (v4.2)

**Night Shift** is an **Autonomous Agent Orchestrator** where the **Brain (Director)** and **Hassan (Worker)** collaborate to finish your projects while you're away. 

v4.2 is a major leap forward, moving away from API SDKs to **Pure CLI Tools** and introducing advanced agentic features like Cross-verification, Long-term Memory, and Parallel Execution.

---

## ✨ Why Night Shift? (Advanced Features)

*   **🧠 Pure CLI Brain (Director)**: No more API SDKs. Night Shift uses your installed `claude`, `gemini`, or `codex` CLIs directly as its "intellect."
*   **🏘️ Brain's Own Room (Shadow Workspace)**: The Brain thinks inside its own private sanctuary (`.night_shift/brain_env`). Your actual workspace and the Brain's internal monologues never mix.
*   **🦾 The Hassan (Worker)**: World-class execution using CLI drivers like `Claude Code` to modify code and run tests.
*   **🕵️‍♂️ The Critic (Dual-Brain QA)**: Every completed task is cross-verified by a separate AI persona (the Critic). If it's not perfect, Hassan goes back to work.
*   **📚 Memories of the Night**: Brain now stores "Lessons Learned" in `.night_shift/memories.md` after every mission, ensuring it avoids past mistakes and gets smarter over time.
*   **⚡ The Squad (Parallel Mode)**: Need speed? Enable `parallel: true` in your mission to spawn multiple Hassans in isolated workspaces to tackle independent goals simultaneously.
*   **⏪ Safety Net (Auto-Rollback)**: Before every task, Night Shift creates a Git checkpoint. If a task fails, it automatically rolls back to a clean state.
*   **🎭 Dynamic Personas**: Switch between **Architect, Troubleshooter, Brainstormer, Researcher, or Documenter**. Both the Brain and Hassan adopt the same professional identity for maximum synergy.
*   **⏳ The Patient Waiter**: Automatically handles quota limits with a live countdown—it waits persistently until the API resets.

---

## 🚀 Getting Started

### 1. Preparation
Log in to your preferred CLI tools beforehand.
```bash
claude login  # or gemini login, codex login
```

### 2. Configuration (`settings.yaml`)
Configure your drivers and personas. See `docs/templates/` for examples.

```yaml
brain:
  active_driver: "claude"
  claude:
    command: "claude"
    args: ["-p", "{prompt}", "--dangerously-skip-permissions"]
body: # or "hassan" for backward compatibility
  active_driver: "claude"
critic:
  active_driver: "gemini" # Use a different model for best QA results!

safety:
  auto_rollback_on_failure: false
  create_backup_branch: true
  auto_commit_and_push: false
```
Note: `drivers:` is no longer required; driver configs sit directly under each block.

Optional additions:
- `tools`: shared tool registry inserted into Brain/Hassan prompts.
- `planner.enabled`: auto-expands goals into a task list (approval optional).
- `qa.run_tests`: runs tests after tasks or per task.
- `memory.scope`: `project`, `global`, or `both`.
- `parallel.max_workers` + `parallel.use_worktrees`: control parallel execution.

Notes:
- `auto_commit_and_push` is opt-in; leave false for manual review.
- `create_backup_branch` creates a backup branch without switching to it.

### 3. Define Your Mission (`mission.yaml`)
```yaml
mission_name: "Example Mission"
goal:
  - "Design a MessageBus class."
  - "Implement unit tests."
persona: "architect"
parallel: false # Set to true for SQUAD power
```
Note: `task` is still supported for backward compatibility, but `goal` is preferred.

Reviewer-only mode (no execution):
```yaml
reviewer_mode: true
```

Per-task persona (optional):
```yaml
goal:
  - task: "Design the architecture and modules."
    persona: "architect"
  - task: "Write README and usage docs."
    persona: "documenter"
```

Automatic persona selection (optional, in settings.yaml):
```yaml
persona_rules:
  - pattern: "docs|readme|document"
    persona: "documenter"
    flags: "i"
  - pattern: "bug|error|fix"
    persona: "troubleshooter"
    flags: "i"
```

### 4. Launch the Overlord
```bash
python3 night_shift.py mission.yaml
```

Init is no longer supported. Use templates instead.

Common flags:
- `--reviewer` review-only mode
- `--persona-map "pattern:persona"` quick persona rules
- `--log-level DEBUG` and `--log-dir logs`

Templates & examples:
- `docs/templates/` for common mission types
- `docs/hello_world/` for a minimal working example

---

## 📂 The New Folder Structure

*   `night_shift.py`: The command center.
*   `.night_shift/brain_env`: Brain's private quarters & isolated sessions.
*   `.night_shift/memories.md`: The Brain's long-term memory vault.
*   `.night_shift/squad/`: Temporary isolated workspaces for parallel tasks.
*   `logs/`: Strategic and runtime logs.
*   `logs/night_shift_summary_...`: JSON summary of tasks, personas, and timings.

Optional:
- `.night_shiftignore` to exclude directories from workspace cloning.

---

## ⚠️ Safety Notice

This tool executes AI agents with **file modification and deletion permissions**.
*   **Backups are mandatory.** Night Shift is powerful but autonomous.
*   Automatic Git snapshots are enabled by default—make sure you're in a Git repo!

---

## 🤝 Contribution

If you like this toy project, feel free to contribute. Night Shift is here to take the night shift for you! 😴✨
