# 🌙 Night Shift: The Autonomous Overlord (v4.4)

**Night Shift** is an **Autonomous Agent Orchestrator** where the **Brain (Director)** and **Hassan (Worker)** collaborate to finish your projects while you're away. 

v4.4 is a major leap forward, moving away from API SDKs to **Pure CLI Tools** and introducing advanced agentic features like Cross-verification, Long-term Memory, and Parallel Execution.

---

## ✨ Why Night Shift?

*   **🧠 Pure CLI Brain**: Uses your installed `claude`, `gemini`, or `codex` CLIs directly—no API SDKs required.
*   **🕵️‍♂️ Dual-Brain QA**: Every task is cross-verified by the Critic (a separate AI persona). If imperfect, Hassan iterates automatically.
*   **📚 Long-Term Memory**: Stores lessons learned in `.night_shift/memories.md` to avoid repeating past mistakes across missions.
*   **⚡ Parallel Execution**: Enable `parallel: true` to spawn multiple Hassans in isolated workspaces for simultaneous task completion.
*   **⏪ Safety Net**: Automatic Git checkpoints before each task with auto-rollback on failure.
*   **🎭 Dynamic Personas**: Architect, Troubleshooter, Documenter modes—synchronized across Brain and Hassan for consistent execution.

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
- `docs/features.md` for capability overview and key settings

## ⚙️ Configuration (`settings.yaml`)

Configure your drivers and personas. See `docs/templates/` for examples.

### Basic Configuration

```yaml
brain:
  active_driver: "claude"
  home_dir: ".night_shift/brain_env" # Isolated environment for Brain
  link_auth: true # Link authentication from ~/.claude, ~/.gemini, etc.
  claude:
    command: "claude"
    args: ["-p", "{prompt}", "--dangerously-skip-permissions"]

body: # Configuration key is "body" (Hassan is the nickname for the worker)
  active_driver: "claude"

critic:
  active_driver: "gemini" # Use a different model for best QA results!
  home_dir: ".night_shift/critic_env" # Isolated environment for Critic
  link_auth: true
  strictness: "lenient" # lenient | balanced | strict
  enabled: true # Set false to disable critic checks

safety:
  auto_rollback_on_failure: false
  create_backup_branch: true
  auto_commit_and_push: false # Opt-in feature; leave false for manual review
```

**Notes:**
- `home_dir`: Creates an isolated environment directory for Brain/Critic sessions
- `link_auth`: Automatically links authentication files from your home directory
- `auto_commit_and_push`: Disabled by default for safety; enable only if you trust the autonomous workflow
- `context_reduction`: Trims long history to reduce token usage

### Full Settings Reference

```yaml
brain:
  active_driver: "claude" # claude | gemini | codex
  output_format: "text" # text | json
  home_dir: ".night_shift/brain_env" # Isolated environment directory
  link_auth: true # Link ~/.claude, ~/.gemini auth to isolated env

  claude:
    command: "claude"
    args: ["-p", "{prompt}"]
  gemini:
    command: "gemini"
    args: ["-p", "{prompt}"]
  codex:
    command: "codex"
    args: ["exec", "--full-auto", "{query}"]

critic:
  active_driver: "gemini"
  home_dir: ".night_shift/critic_env"
  link_auth: true
  strictness: "lenient" # lenient | balanced | strict
  enabled: true # Set false to disable critic checks

  # Advanced: Multi-Critic Voting (requires multiple models)
  active_drivers: ["gemini", "codex"] # Enable multi-critic consensus
  voting: "all" # all = unanimous | majority = 50%+ agreement

  gemini:
    command: "gemini"
    args: ["-p", "{prompt}"]
  codex:
    command: "codex"
    args: ["exec", "--full-auto", "{prompt}"]

body:
  active_driver: "claude"
  claude:
    command: "claude"
    args: ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}"]
    env: {} # Optional environment variables
  codex:
    command: "codex"
    args: ["exec", "--full-auto", "{query}"]

safety:
  auto_rollback_on_failure: false # Auto-rollback on task failure
  create_backup_branch: false # Create backup branch before mission
  auto_commit_and_push: false # Auto-commit and push after completion
  require_approval_for_destructive: true # Prompt before rm -rf, git reset, etc.
  preview_changes: false # Run tasks in worktree and preview before applying
  use_worktrees: false # Use git worktrees for task isolation

tools:
  - "rg -n <pattern> <path>" # Shared tool registry for Brain/Hassan prompts
  - "python3 night_shift.py --dry-run"

planner:
  enabled: false # Auto-expand goals into detailed task lists
  require_approval: true # Prompt before accepting planner output

qa:
  run_tests: false # Run tests after tasks
  test_on_each_task: true # Run tests after each task (vs. only at end)
  test_command: "" # e.g. "pytest -q" or "npm test"

memory:
  scope: "project" # project | global | both

parallel:
  max_workers: 4 # Maximum parallel Hassan workers
  use_worktrees: false # Use git worktrees for parallel tasks

context_reduction:
  enabled: true # Trim long history to reduce tokens
  head_chars: 800
  tail_chars: 2000

resume: true # Resume unfinished missions after interruption

personas:
  architect: |
    - Focus on high-level structure, scalability, and design patterns.
    - Avoid quick hacks; prioritize maintainability.

  troubleshoot: |
    - Prioritize root cause analysis (RCA).
    - Always analyze logs and tracebacks before proposing fixes.

  document: |
    - Write professional, clear, and concise technical documentation.
    - Focus on the "Why" and "How to use" rather than just the "What".

  general: |
    - Act as a balanced, professional software engineer.

persona_rules:
  - pattern: "docs|readme|document"
    persona: "document"
    flags: "i" # Case-insensitive regex matching
  - pattern: "bug|error|traceback|fix"
    persona: "troubleshoot"
    flags: "i"
```

Supported personas:
- architect
- troubleshoot
- document
- brainstorm
- research
- analyze
- general
- security
- performance
- testing
- ops
- researcher
- refactor
- ux_writer

---

## 📋 Define Your Mission (`mission.yaml`)

```yaml
mission_name: "Example Mission"
project_path: "."
persona: "architect"
parallel: false # Set to true for parallel task execution

goal:
  - "Design a MessageBus class."
  - "Implement unit tests."

constraints:
  - "Use only standard libraries."
```

**Note**: `task` is still supported for backward compatibility, but `goal` is preferred.

### Per-Project Overrides

You can override `brain`, `body`, and `critic` per mission. If omitted, `settings.yaml` is used.
```yaml
brain:
  active_driver: "gemini"
body:
  active_driver: "claude"
critic:
  active_driver: "codex"
```

### Full Mission Reference
```yaml
mission_name: "Example Mission"
project_path: "."
persona: "general"
parallel: false
reviewer_mode: false

goal:
  - "Simple string task"
  - task: "Task with persona"
    persona: "architect"
  - title: "Hierarchical Task"
    persona: "document"
    sub_tasks:
      - "Sub task A"
      - "Sub task B"

constraints:
  - "Use only standard libraries."
```

### Reviewer Mode

Set `reviewer_mode: true` in `mission.yaml` or use the `--reviewer` flag to run Night Shift in **review-only mode**. The Brain will analyze your code and provide feedback **without executing any changes**.

```yaml
reviewer_mode: true

goal:
  - "Review the security of the auth module."
  - "Analyze performance bottlenecks in the API."
```

### Per-Task Personas

```yaml
goal:
  - task: "Design the architecture and modules."
    persona: "architect"
  - task: "Write README and usage docs."
    persona: "document"
```

### Automatic Persona Selection

Define patterns in `settings.yaml` to automatically select personas:

```yaml
persona_rules:
  - pattern: "docs|readme|document"
    persona: "document"
    flags: "i"
  - pattern: "bug|error|fix"
    persona: "troubleshoot"
    flags: "i"
```

---

## 🏃 Launch the Overlord
```bash
python3 night_shift.py mission.yaml
```

**Note**: The `--init` command was removed in v4.3.0. Use the template files in `docs/templates/` to get started quickly instead.

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

### Templates & Examples

- `docs/templates/`: Common mission types (bugfix, refactor, documentation, subtasks)
- `docs/hello_world/`: Minimal working example

---

## 📂 Folder Structure

*   `night_shift.py`: The command center.
*   `.night_shift/brain_env`: Brain's private quarters & isolated sessions.
*   `.night_shift/critic_env`: Critic's isolated analysis environment.
*   `.night_shift/memories.md`: The Brain's long-term memory vault.
*   `.night_shift/squad/`: Temporary isolated workspaces for parallel tasks.
*   `logs/`: Strategic and runtime logs.
*   `logs/night_shift_summary_...`: JSON summary of tasks, personas, and timings.

**Optional:**
- `.night_shiftignore`: Exclude directories from workspace cloning (similar to `.gitignore`)

---

## ❓ FAQ

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

---

## 🔧 Troubleshooting

**"Command not found: claude"**
→ Install the CLI tool and ensure it's in your system PATH. Try running `claude --version` manually.

**"Quota exceeded" error**
→ Night Shift automatically waits and retries when quotas are hit. You'll see a countdown timer.

**"Git not initialized" error**
→ Safety features require a Git repository. Run `git init` in your project root.

**Authentication issues**
→ Ensure you've logged in to the CLI tool (`claude login`) before running Night Shift. Set `link_auth: true` to share authentication with isolated environments.

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
