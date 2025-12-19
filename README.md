# 🌙 Night Shift: The Autonomous Overlord (v4.2)

**Night Shift** is more than just a coding assistant. It's an **Autonomous Agent Orchestrator** where two entities—the **Brain (Director)** and **Hassan (Worker)**—collaborate to complete your projects while you sleep (or grab a coffee).

From v4.2, we’ve ditched the clunky API SDKs. Night Shift now runs exclusively using **Pure CLI Tools (Claude Code, Gemini CLI, Codex, etc.)**, making it more powerful, isolated, and lightweight.

---

## ✨ Why Night Shift? (Witty Features)

*   **🧠 Pure CLI Brain (Director)**: Stop hunting for API keys. Night Shift uses your installed `claude`, `gemini`, or `codex` CLIs directly as its "intellect."
*   **🏘️ Brain's Own Room (Shadow Workspace)**: The Brain thinks inside its own private sanctuary (`.night_shift/brain_env`). Your actual workspace and the Brain's internal monologues never mix. It’s "parallel-universe-tier" isolation.
*   **🦾 The Hassan (Worker)**: Let Hassan do the heavy lifting. Using world-class CLI drivers like `Claude Code`, it modifies code, runs tests, and gets its hands dirty.
*   **⏳ The Patient Waiter**: Hit a quota limit? Night Shift doesn't panic. It counts down every minute, waiting persistently until the quota resets so it can resume the mission.
*   **🔄 Stateless OODA Loop**: Observe, Orient, Decide, and Act. By analyzing the full context from scratch in every loop, the Brain avoids getting stuck in past mistakes.
*   **🔌 Zero-SDK Dependency**: Our `requirements.txt` is on a diet. No heavy LLM libraries needed—just your CLI tools and Python.

---

## 🚀 Getting Started

### 1. Preparation
Log in to your preferred CLI tools beforehand. (Auth tokens are shared between the Brain and Hassan seamlessly.)
```bash
claude login  # or gemini login, codex login
```

### 2. Configuration (`settings.yaml`)
Instead of API keys, you now configure executable paths and arguments. Much more intuitive!

```yaml
brain:
  active_driver: "claude" # The smart guy who strategizes
  drivers:
    claude:
      command: "claude"
      args: ["-p", "{prompt}", "--dangerously-skip-permissions"]

hassan: # The strong guy who executes
  active_driver: "claude"
  drivers:
    claude:
      command: "claude"
      args: ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}", "-c", "--dangerously-skip-permissions"]
```

### 3. Run Your Mission
Define your goals in `mission.yaml` and launch the overlord.
```bash
python3 night_shift.py mission.yaml
```

---

## 📂 The New Folder Structure

*   `night_shift.py`: The command center.
*   `.night_shift/brain_env`: The Brain’s private quarters (session data is isolated here).
*   `logs/`: The secret diaries of both entities.
    *   `night_shift_log_...`: Overall runtime logs.
    *   `brain_log_...`: Detailed logs of the Brain’s strategic thinking.
    *   `night_shift_history_...`: A full report of the session history.

---

## ⚠️ Safety Notice (The "Adults Only" Rule)

This tool automatically executes AI agents with **file modification and deletion permissions**.
*   **Backups are mandatory.** Night Shift loves your code, but sometimes it shows its love a bit too aggressively.
*   The `--dangerously-skip-permissions` flag is often enabled by default. Double-check your `mission.yaml` before hitting start.

---

## 🤝 Contribution

If you like this toy project, feel free to tinker with it and make it better. After all, Night Shift can take the night shift for you! 😴✨