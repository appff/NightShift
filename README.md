# 🌙 Night Shift: The Autonomous Overlord

**Night Shift** is an **Autonomous Agent Orchestrator** where the **Brain (Director)** and **Hassan (Worker)** collaborate to finish your projects while you're away. 

**v5.1** introduces a new **project-centric workflow**. Instead of defining a list of goals, you now manage a single `mission.yaml` file as a persistent dashboard for your entire project, tracking task status directly within the file.

---

## ✨ Why Night Shift (v5.1)?

*   **🧠 Cognitive Architecture (SuperClaude Inspired)**: Agents think and act like specialized experts, learning from past mistakes (`ReflexionMemory`) and verifying their own work (`SelfCheckProtocol`).
*   **📋 Project-as-a-Dashboard**: The `mission.yaml` file is now a living document. Task statuses (`todo`, `in_progress`, `done`) are updated directly in the file, providing a single source of truth for your project's progress.
*   **🎭 Dynamic Persona Selection**: Let `persona_rules` in `settings.yaml` intelligently select the best expert for each task, or assign them manually.
*   **🚀 Token Efficiency (Layer 0 Bootstrap)**: Minimizes token usage by loading only essential project context (file tree, `README.md`) initially.
*   **🛡️ Robust Quality Gates**: Ensures tasks are not just "done," but done *right* through rigorous, persona-aware self-validation.
*   **⚡ Parallel Execution**: Run independent tasks simultaneously by setting `parallel: true`.
*   **⏪ Safety Net**: Automatic Git checkpoints and auto-rollback on failure.

---

## 🚀 Quick Start (v5.1 Project-Based Workflow)

### Step 1: Initialize Your Project

For a new or existing project, create a `mission.yaml` file in your project's root. This file will be your main dashboard.

**`mission.yaml`**
```yaml
project:
  project_root: "." # Defines the root directory for this mission
  # project_name: "My Awesome Project" # Optional

mission:
  title: "Develop a new feature and document it"
  persona: "general" # Default persona for all tasks
  constraints:
    - "Use Python 3.11+"
    - "All code must be formatted with black."

tasks:
  - id: "task_001"
    title: "Design the core module"
    persona: "system-architect" # Override persona for a specific task
    status: "todo"

  - id: "task_002"
    title: "Implement the feature with unit tests"
    depends_on: ["task_001"] # Optional dependency
    status: "todo"

  - id: "task_003"
    title: "Write user documentation for the new feature"
    persona: "technical-writer"
    depends_on: ["task_002"]
    status: "todo"
```

### Step 2: Run Night Shift

Simply execute Night Shift, pointing it to your mission file.

```bash
# Ensure you are in the directory containing mission.yaml
nightshift mission.yaml
```

### Step 3: Observe and Collaborate

-   Night Shift will find the first task with `status: "todo"` and start working on it.
-   Once `task_001` is complete, Night Shift will **automatically update** `mission.yaml` to mark it as `status: "done"`.
-   It will then proceed to the next `todo` task. You can stop and resume at any time.

This new project-based approach makes long-term, multi-task projects much easier to manage.

---

## 📚 Documentation

- `docs/architecture.md`: System structure and data flow.
- `docs/features.md`: Capability overview and all available personas.
- `docs/quality_gates.md`: How Night Shift ensures "true completion".

## ⚙️ Configuration

For detailed configuration of drivers (AI models), safety settings, and persona rules, see `settings.example.yaml`.
