# 🌙 Night Shift: The Autonomous Overlord

**Night Shift** is a command-line-native **Autonomous Agent Orchestrator** designed to reliably execute complex software engineering tasks. It acts as a tireless collaborator that works on your projects, finishes tasks, and verifies its own work, allowing you to delegate with confidence.

### How It Works: A Two-Agent System

Night Shift's architecture is simple and robust, centered around two distinct agent roles that collaborate in a loop:

1.  **The Brain (Director/Auditor)**:
    *   **Role**: The project manager and quality assurance lead. It is a high-level LLM agent that interprets your `mission.yaml` file.
    *   **Function**: It breaks down high-level goals into a series of precise, executable commands. Crucially, it then **verifies** the outcome of each command by inspecting file content, logs, or command outputs before proceeding. Its core identity is that of a strict auditor, ensuring tasks are not just *attempted*, but verifiably *completed*.

2.  **The Worker (Hassan)**:
    *   **Role**: The hands-on developer. It is a CLI-driven agent that has no long-term memory or planning capability.
    *   **Function**: It receives single, explicit commands from the Brain and executes them. This can range from writing code, running tests, fetching data, to creating files.

This separation of duties—strategic planning and verification (Brain) vs. simple execution (Worker)—creates a reliable, debuggable, and effective workflow.

### 📋 System Requirements

To run Night Shift effectively, ensure your system meets the following requirements:

- **OS**: macOS or Linux (WSL2 supported)
- **Python**: 3.10 or higher
- **Node.js & npm**: Required for certain MCP servers (e.g., `sequential_thinking`)
- **uv**: Required for high-performance MCP server management (e.g., `serena`)
- **Git**: Night Shift works best within a Git repository for safety and state management.
- **LLM CLI**: At least one supported LLM CLI installed and configured:
  - `claude` (Claude Code CLI)
  - `gemini` (Google Gemini CLI)
  - `ollama` (For local models like DeepSeek-R1, Qwen2.5, Llama3.1)
  - `@openai/codex` (Codex CLI)

### Core Philosophy

*   **Autonomy Through Verification**: True autonomy isn't just about executing commands; it's about achieving a goal. Night Shift's **Evidence-Based Done** protocol requires the Brain to find physical proof of completion, significantly reducing agent hallucinations and incomplete work.
*   **CLI-Native**: Designed for developers, Night Shift operates directly on your filesystem using familiar command-line tools. It is not a chatbot in a browser window.
*   **Model-Agnostic**: Leverage the power of any local or remote LLM that has a CLI wrapper (Ollama, Claude, Gemini, etc.).

**v5.7** introduces the leaner, more robust **Evidence-Based Architecture**. By unifying verification into the Brain's core identity, Night Shift ensures high-quality results with reduced complexity and faster execution.

---

## ✨ Why Night Shift (v5.7)?

*   **🔍 Evidence-Based Done**: The Brain (Director) no longer blindly trusts the Worker's reports. Completion is only granted when **physical evidence** (file content, test logs, or command output) is visible in the session history.
*   **⚖️ Brain as Auditor & Architect**: The Brain's identity is fixed as a high-level Auditor. It remains objective and skeptical, ensuring the Worker (Hassan) adheres to mission constraints regardless of their persona.
*   **🛠️ Optimized for Local LLMs**: Enhanced support for models like DeepSeek, Qwen, and Llama via **Smart Tools** (`view`, `list`, `edit`). Advanced prompt engineering combats recency bias in local models.
*   **📉 Lean Orchestration**: The separate Critic module has been integrated into the Brain's verification logic, reducing token overhead and eliminating agent-to-agent friction.
*   **🧠 Cognitive Architecture**: Agents learn from past mistakes (`ReflexionMemory`) and apply rigorous structural integrity checks before declaring a mission success.
*   **🧩 Batch Mode + Smart Hassan**: Deterministic multi-step tasks can run in a single batch, with optional safe auto-fix on failures.
*   **🔌 MCP Support**: Seamlessly integrate external tools and memory via Model Context Protocol (Serena, Sequential Thinking, etc.).
*   **📉 Message Efficiency**: Suppress redundant persona text in long sessions to save tokens and costs.
*   **📋 Project-as-a-Dashboard**: Manage your entire project via `mission.yaml`. Statuses (`todo`, `in_progress`, `done`) update in real-time as the dashboard evolves.
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
- **Auto-install MCP servers** (Serena, etc.) if `uv` and `npm` are detected.
- Add the `nightshift` command to your `PATH`

*To update your installation, simply run the same command again.*

---

## 🚀 Quick Start (v5.7 Project-Based Workflow)

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

- **Strict Audit**: The Brain will command `view` or `read_file` to verify the Worker's output before finishing.
- **Auto-Injection**: Night Shift will automatically add `id: task_n` and `status: todo` to tasks.
- **State Tracking**: Statuses update from `todo` → `in_progress` → `done` directly in your YAML.
- **Persistence**: Stop and resume exactly where you left off.

---

## 📚 Documentation

- `docs/architecture.md`: System structure and data flow (v5.7 Auditor Model).
- `docs/features.md`: Capability overview and all available personas.
- `docs/quality_gates.md`: How Night Shift ensures "true completion".

## ⚙️ Configuration

Configure Night Shift via `settings.yaml` in the project root. Key sections include:

### 🧠 Intelligence (Brain & Body)
*   `active_driver`: Choose your LLM engine (e.g., `claude`, `gemini`, `deepseek`, `llama`).
*   `output_format`: Set to `json` for more reliable autonomous operation.

### 🛡️ Safety & Verification
*   `auto_rollback_on_failure`: Roll back changes if a task fails.
*   `require_approval_for_destructive`: Gate commands like `rm -rf`.
*   `qa.run_tests`: Automatically run your test suite after tasks.

### 📉 Efficiency & Context
*   `message_efficiency`: Set to `true` to save tokens by suppressing redundant persona text.
*   `context_reduction`: Automatically trim long conversation history.
*   `batch.enabled`: Allow the Brain to emit batch command plans for deterministic tasks.
*   `body.autonomy`: Enable Smart Hassan behavior (`basic`, `moderate`, `high`), including optional batch execution.
*   `body.auto_fix`: Allow Smart Hassan to attempt safe auto-fixes after batch failures.

### 🔌 Model Context Protocol (MCP)
NightShift can connect to any MCP-compliant server. You can globally disable MCP by setting `mcp_enabled: false`.

```yaml
mcp_enabled: true
mcp_servers:
  serena:
    command: "uvx"
    args: ["--from", "git+https://github.com/oraios/serena.git", "serena", "start-mcp-server"]
  sequential_thinking:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sequential-thinking"]
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

*   **SuperClaude**: The specialized personas used in this project are derived from the [SuperClaude](https://github.com/SuperClaude-Org) framework, which is licensed under the MIT License. We thank the SuperClaude community for their contributions to prompt engineering.
