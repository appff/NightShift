# 🌙 Night Shift: The Autonomous Overlord

**Night Shift** is an **Autonomous Agent Orchestrator** where the **Brain (Director)** and **Hassan (Worker)** collaborate to finish your projects while you're away. 

**v5.0** marks a significant milestone, integrating a **SuperClaude-inspired Cognitive Architecture** that makes Night Shift dramatically more intelligent, robust, and token-efficient. It moves beyond simple task execution to advanced self-learning and quality assurance.

---

## ✨ Why Night Shift (v5.0)?

*   **🧠 Cognitive Architecture (SuperClaude Inspired)**: Night Shift now thinks like a multi-specialist team, powered by:
    *   **Reflexion Memory**: Learns from past mistakes (Error -> Root Cause -> Fix) to avoid repetition.
    *   **Persona-Driven Behavior**: Agents adopt specialized mindsets (e.g., `backend-architect`, `security-engineer`) based on task needs, defined in rich Markdown files.
    *   **Confidence Check (Pre-flight)**: Assesses task feasibility before execution, preventing "running blind."
    *   **Self-Check Protocol (Post-flight)**: Enforces strict quality gates (the "4 Questions") to ensure "true completion" with evidence.
*   **🚀 Token Efficiency (Layer 0 Bootstrap)**: Intelligently loads only essential project context (file tree, `README.md`) initially, minimizing token usage and speeding up task planning.
*   **🕵️‍♂️ Quality Gates**: Beyond simple criticism, the `SelfCheckProtocol` ensures that tasks are not just "done" but done *right*, according to professional standards and persona expectations.
*   **📚 Long-Term Memory**: Stores lessons learned in `.night_shift/reflexion.jsonl` (for errors) and `.night_shift/memories.md` (for general insights).
*   **⚡ Parallel Execution**: Enable `parallel: true` to spawn multiple Hassans in isolated workspaces for simultaneous task completion.
*   **⏪ Safety Net**: Automatic Git checkpoints before each task with auto-rollback on failure.
*   **🎭 Dynamic Persona Selection**: Choose specific personas in `mission.yaml` or let `persona_rules` in `settings.yaml` intelligently select the best expert for the job.

---

## 🚀 Quick Start (30 seconds)

1.  **Install & Login**: Ensure you have a CLI tool installed and logged in.
    ```bash
    claude login  # or gemini login
    ```
2.  **Create a Mission**:
    ```bash
    cp docs/templates/mission_docs.yaml mission.yaml
    ```
3.  **Run Night Shift**:
    ```bash
    python3 night_shift.py mission.yaml
    ```

That's it! See detailed configuration below.

---

## 📚 Documentation

- `docs/architecture.md` for system structure and data flow
- `docs/features.md` for capability overview and key settings (including available personas)
- `docs/quality_gates.md` for understanding Night Shift's advanced completion verification

## ⚙️ Configuration (`settings.yaml`)

Configure your drivers, personas, and safety features. See `docs/templates/` for example mission files.

### Basic Configuration

```yaml
brain:
  active_driver: "claude"
  output_format: "json" # json is highly recommended for structured reasoning
  timeout: 300           # Seconds to wait for Brain response

hassan: # Configuration key is "hassan" (was "body")
  active_driver: "claude"
  timeout: 600

critic:
  enabled: true # Set false to disable critic checks
  active_drivers: [gemini] # Can use multiple critics for voting
  voting: majority         # all (unanimous) or majority
  timeout: 300

safety:
  auto_rollback_on_failure: true
  create_backup_branch: true
  auto_commit_and_push: false # Disabled by default for safety; enable only if you trust the autonomous workflow
  require_approval_for_destructive: true
  preview_changes: false # If true, uses worktrees to preview changes before applying
  use_worktrees: false # Use git worktrees for task isolation

memory:
  scope: project # project, global, or both

# Dynamic Persona Selection (new in v5.0)
persona_rules:
  # Example: If task description contains 'backend' or 'api', use 'backend-architect' persona
  - pattern: "(?i)(backend|api|database)"
    persona: "backend-architect"
  - pattern: "(?i)(security|vulnerability)"
    persona: "security-engineer"
  # ... more rules defined in settings.example.yaml
```

**Notes:**
- `home_dir` / `link_auth`: These are automatically handled by Night Shift based on `project.project_root` for isolated environments.
- Persona files default to `<mission.yaml directory>/personas`. Override with `personas_root` in `settings.yaml` or `mission.yaml` if needed.
- `context_reduction`: Trims long history to reduce token usage.
- `approval` / `sandbox`: Optional Codex-only flags; applied only if your Codex CLI supports these flags.

### Full Settings Reference (`settings.example.yaml`)

For a comprehensive list of all configurable options and examples, refer to `settings.example.yaml` in the project root.

---

## 📋 Define Your Mission (`mission.yaml`)

```yaml
project:
  name: "Example Mission"
  project_root: "."
  owner: ""
  tags: ["example"]

mission:
  name: "Example Mission"
  status: "active"
  created_at: "2025-01-01"
  updated_at: "2025-01-01"
  persona: "system-architect" # Specify a persona from the 'personas/' directory

parallel: false # Set to true for parallel task execution

tasks:
  - id: "EX-001"
    title: "Design a MessageBus class using SOLID principles."
    status: "todo"
    priority: "P1"
  - id: "EX-002"
    title: "Implement unit tests for the MessageBus."
    status: "todo"
    priority: "P1"
  - id: "EX-003"
    title: "Document the design choices and API."
    status: "todo"
    priority: "P2"

constraints:
  - "Use only standard Python libraries."
  - "Ensure 95% test coverage."
```

**Note**: `project.project_root` can point to any project directory (git repo not required). `tasks` are tracked in `mission.yaml` and updated automatically as they move from `todo` → `in_progress` → `done` (or `blocked` on failure).
Legacy `mission.yaml` files can be migrated with `scripts/migrate_mission_v4_to_v5.py`.

### Full Mission Reference & Templates

Refer to `docs/templates/` for various mission examples (bugfix, refactor, documentation, subtasks) and `docs/features.md` for a complete list of available personas.

---

## 🏃 Launch the Overlord
```bash
python3 night_shift.py mission.yaml
```

### Common Flags

- `--reviewer`: Review-only mode (no execution)
- `--auto-approve-plan`: Auto-approve planner output without prompting
- `--auto-approve`: Auto-approve destructive actions and preview changes
- `--persona-map "pattern:persona"`: Quick persona rules (regex patterns)
- `--log-level DEBUG`: Set logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `--log-dir logs`: Specify log directory
- `--dry-run`: Validate config files and exit

### Common Workflows

- **Planner with approval**: Set `planner.enabled: true` and `planner.require_approval: true`
- **Safety preview**: Set `safety.preview_changes: true` (runs tasks in worktrees, asks to apply changes)
- **Destructive action gate**: Keep `safety.require_approval_for_destructive: true`
- **Tests after each task**: Set `qa.run_tests: true` and `qa.test_on_each_task: true`

---

## 📂 Folder Structure

*   `night_shift.py`: The command center.
*   `.night_shift/brain_env`: Brain's private quarters & isolated sessions.
*   `.night_shift/critic_env`: Critic's isolated analysis environment.
*   `.night_shift/memories.md`: The Brain's general long-term memory vault.
*   **`.night_shift/reflexion.jsonl`**: **New in v5.0!** Structured memory for learning from past errors.
*   `.night_shift/squad/`: Temporary isolated workspaces for parallel tasks.
*   `logs/`: Strategic and runtime logs.
*   `logs/night_shift_summary_...`: JSON summary of tasks, personas, and timings.
*   `personas/`: **New in v5.0!** Directory containing rich Markdown persona definitions.

**Optional:**
- `.night_shiftignore`: Exclude directories from workspace cloning (similar to `.gitignore`)

---

## ❓ FAQ

**Q: What is Night Shift v5.0 about?**
A: v5.0 introduces a **Cognitive Architecture** inspired by SuperClaude, bringing advanced features like persona-driven behavior, intelligent self-validation (Confidence Check, Self-Check Protocol), and token optimization for more robust and efficient autonomous execution.

**Q: Do I need API keys?**
A: No! Night Shift uses CLI tools that you log into separately (`claude login`, `gemini login`, etc.). No API keys needed.

**Q: What's the difference between Brain and Hassan?**
A: **Brain** = Strategic planner and director. **Hassan** = Code executor and worker.

**Q: Can I use multiple AI models?**
A: Yes! Use different models for Brain, Critic, and Hassan for best results. Example: Claude for Brain, Gemini for Critic.

**Q: What is Multi-Critic Voting?**
A: Enable `active_drivers: ["gemini", "codex"]` under `critic` to have multiple AI models review each task. Use `voting: "all"` for unanimous consensus or `voting: "majority"` for 50%+ agreement.

**Q: How does parallel execution work?**
A: Set `parallel: true` in your mission. Night Shift spawns multiple Hassan workers in isolated workspaces to execute independent tasks simultaneously.

**Q: How does Night Shift ensure code quality (Quality Gates)?**
A: Night Shift implements a multi-stage validation process. A **Confidence Check** assesses task feasibility before execution, and a **Self-Check Protocol** (with persona-aware validation) rigorously verifies completion *after* execution, ensuring tasks are done correctly and completely.

---

## 🔧 Troubleshooting

**"Command not found: claude"**
→ Install the CLI tool and ensure it's in your system PATH. Try running `claude --version` manually.

**"Quota exceeded" error**
→ Night Shift automatically waits and retries when quotas are hit. You'll see a countdown timer.

**"Git not initialized" error**
→ Safety features require a Git repository. Run `git init` in your project root.

**Authentication issues**
→ Ensure you've logged in to the CLI tool (`claude login`) before running Night Shift.

**"Uncommitted changes" warning during rollback**
→ Night Shift automatically stashes uncommitted changes before rolling back. Your work is safe.

---

## ⚠️ Safety Notice

This tool executes AI agents with **file modification and deletion permissions**.
*   **Backups are mandatory.** Night Shift is powerful but autonomous.
*   Automatic Git snapshots are enabled by default—make sure you're in a Git repo!

---

## 🤝 Contribution

If you like this toy project, feel free to contribute. Night Shift is here to take the night shift for you! 😴✨
