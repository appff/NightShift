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

## 🚀 Installation

The easiest way to install Night Shift (macOS/Linux) is via our one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/appff/NightShift/main/install.sh | bash
```

This script will:
- Clone the repository to `~/.night_shift_app`
- Set up a dedicated Python virtual environment
- Install all dependencies
- Add the `nightshift` command to your `PATH`

*To update your installation, simply run the same command again.*

---

## 🚀 Quick Start (v5.1 Project-Based Workflow)

### Step 1: Initialize Your Project

For a new or existing project, create a `mission.yaml` file in your project's root. This file will be your main dashboard.

**`mission.yaml`**
```yaml
project:
  project_root: "." # Defines the root directory for this mission

mission:
  title: "Develop a new feature and document it"
  persona: "general" # Default persona for all tasks
  constraints:
    - "Use Python 3.11+"
    - "All code must be formatted with black."

tasks:
  - title: "Design the core module"
    persona: "system-architect" # Optional: override persona for a specific task

  - title: "Implement the feature with unit tests"

  - title: "Write user documentation for the new feature"
    persona: "technical-writer"
```

### Step 2: Run Night Shift

Simply execute Night Shift, pointing it to your mission file. Night Shift will automatically manage task IDs and track progress for you.

```bash
# Ensure you are in the directory containing mission.yaml
nightshift mission.yaml
```

### Step 3: Observe and Collaborate

Night Shift is designed to be low-maintenance. When you run it:

- **Auto-Injection**: Night Shift will automatically add `id: task_n` and `status: todo` to any tasks that don't have them. 
- **State Tracking**: As it works, it updates `status` from `todo` → `in_progress` → `done`.
- **Persistence**: Your `mission.yaml` is updated in real-time, allowing you to stop and resume exactly where you left off.
- **Smart Mapping**: If you use a legacy `task` field, it will be automatically mapped to `title`.

*Tip: You can still manually define `id` or `status` if you want specific control, and Night Shift will respect your values.*

This new project-based approach makes long-term, multi-task projects much easier to manage.

---

## 📚 Documentation

- `docs/architecture.md`: System structure and data flow.
- `docs/features.md`: Capability overview and all available personas.
- `docs/quality_gates.md`: How Night Shift ensures "true completion".

## ⚙️ Configuration

For detailed configuration of drivers (AI models), safety settings, and persona rules, see `settings.example.yaml`.
