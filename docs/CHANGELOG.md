# Changelog

All notable changes to Night Shift will be documented in this file.

## [5.1.3] - 2025-12-24
### Added
- **Auto-Task Management**: Task IDs and `status: todo` are now automatically generated if missing in `mission.yaml`.
- **Flexible Persona Loading**: Context loader now silently falls back to default context if a persona file is missing.

### Changed
- **Schema Simplification**: Mission templates and `mission.sample.yaml` have been streamlined to remove redundant fields (`project.name`, `mission.status`, `parallel`, etc.) in favor of the v5.1 project-centric schema.
- **Improved Compatibility**: Orchestrator now automatically maps the legacy `task` field to `title` for better backward compatibility.

## [5.1.0] - 2025-01-05
### Added
- **Repo-Scoped Missions**: `mission.yaml` now tracks task status (`todo` → `in_progress` → `done`/`blocked`) and auto-updates during runs.
- **Mission Locking**: Atomic updates to `mission.yaml` with a lock file to avoid parallel write conflicts.
- **Migration Tool**: Added `scripts/migrate_mission_v4_to_v5.py` for legacy mission schema conversion.

### Changed
- **Project Root Key**: `project.repo_root` renamed to `project.project_root` (no git repo required).
- **Planner Behavior**: Planner is ignored for repo-scoped missions; tasks must be defined explicitly.
- **Persona Resolution**: Persona files now default to the NightShift source `personas/` directory, with optional overrides.

## [4.5.0] - 2025-12-23
### Added
- **Hybrid Observation**: Brain can now execute read-only tools (`ls`, `rg`, `grep`, `read_file`, etc.) directly for instant feedback, bypassing the Hassan worker turn.
- **RAG Memory**: Implemented Semantic Memory (RAG-lite) that retrieves only the top 3 most relevant "Lessons Learned" for each task based on keyword overlap, preventing context overflow.
- **Roadmap**: Added `docs/roadmap.md` to track future architectural improvements.

## [4.4.2] - 2025-12-23
### Added
- **Structured Reasoning**: Brain is now forced to output JSON (`{"command": "...", "status": "..."}`) to prevent conversational loops and improve state tracking.
- **Tail-based Filtering**: Hassan (especially Codex) output is filtered to remove execution logs, code blocks, and metadata, keeping only the final summary for the Brain.
- **Scope Enforcement**: Brain's prompt updated to strictly ignore worker-suggested expansions and focus only on core mission goals.

### Changed
- **Context Management**: Reduced `MAX_CONTEXT_CHARS` and `MAX_HISTORY_CHARS` to prevent "Argument list too long" errors in CLI drivers.
- **Auth Fix**: Brain process now inherits system `HOME` to ensure stable access to authentication tokens (e.g., `.anthropic`, `.claude`).
- **Git Diff Truncation**: Large diffs are automatically truncated in the Brain's context to maintain focus and save tokens.
- **Prompt Engineering**: Overhauled Brain prompt with "Strict Director" persona and recency-bias optimization.

## [4.3.1] - 2025-12-22

### Changed
- **Auth Handling**: Auto venv re-exec, auth file linking, and more robust home directory handling.
- **Critic**: Strictness setting support and validation fixes.

## [4.3.0] - 2025-12-22

### Changed
- **Safety Defaults**: Added `auto_commit_and_push` and clarified safer defaults in `settings.yaml`.
- **Rollback Safety**: Automatic rollback now stashes uncommitted changes before resetting.
- **Per-Task Personas**: Goals can set `persona` per task, and optional `persona_rules` can auto-select a persona.
- **Settings Schema**: Driver configs can be defined directly under `brain`, `critic`, and `body` without a `drivers` block (backward compatible).
- **Planner**: Optional planner can expand a mission into tasks (with approval).
- **Tool Registry**: Shared tools list injected into Brain/Hassan prompts.
- **Reviewer Mode**: Added review-only mode for non-executing analysis.
- **Safety Gates**: Optional approval for destructive actions and worktree preview before applying changes.
- **QA**: Optional test enforcement per task or after mission completion.
- **Observability**: JSON run summaries and configurable log level/dir.
- **Docs**: Added mission templates and a hello world example.
- **CLI**: Removed `--init`; use templates instead.

### Removed
- **Dependencies**: Removed `pexpect` from `requirements.txt` (no longer used).

## [4.2.0] - 2025-12-19

### 🚀 Pure CLI & Shadow Workspace (Current)

#### New Features
- **Pure CLI Brain**: Introduced a structure that uses `claude`, `gemini`, and `codex` CLIs directly as the "Brain," replacing the removed API SDKs (google-genai, openai, anthropic).
- **Shadow Workspace (HOME Isolation)**: Injects a dedicated `HOME` environment variable (`.night_shift/brain_env`) during Brain execution to completely isolate session data and metadata from the worker (Hassan).
- **Auth Symlinking**: Automatically links authentication info from the actual `$HOME` (e.g., `.claude`, `.gemini`) to the isolated environment to maintain login status.
- **Interactive Quota Countdown**: Added a countdown feature that notifies the user of the remaining wait time every minute when a quota limit is reached.
- **Relative Quota Parsing**: Supports parsing relative time formats like Gemini CLI's "reset after 1h17m."
- **Brain Execution Timeout**: Implemented a 5-minute timeout to prevent infinite loops or response delays from the Brain.

#### Changed
- **Settings Optimization**: Simplified the driver-centric structure by removing obsolete API Key and model name fields.
- **Dependency Cleanup**: Removed heavy LLM SDKs from `requirements.txt` (lightweight).

#### Removed
- **Aider Driver**: Deleted code and guides related to the `aider` driver due to low usage and redundancy.

---

## [4.1.0] - 2024-12-18

### 🚀 Sequential Tasking & Rebranding

#### New Features
- **Sequential Task Execution**: Introduced the ability to receive the `goal` in `mission.yaml` as a list and process each item sequentially.
- **Logging Module**: Completely replaced `print`-based logging with the Python standard `logging` module to support log level management and dual output (file/console).
- **Dynamic System Prompt**: Updates the system prompt file via `Hassan.prepare()` every time a task changes.

#### Changed
- **Rebranding**: Renamed the execution unit (Actor/Body) to **`Hassan`**.
- **Validation**: Added logic to strictly validate whether the `goal` field in `mission.yaml` is a string or a list of strings.

---

## [4.0.0] - 2024-12-18

### 🚀 Brain & Body Architecture (Major Update)

#### New Architecture
- **Brain & Body Separation**: Clearly separated the roles of `Brain` (strategist) and `Body` (executor) to enhance modularity.
- **Pluggable Drivers**: Introduced a structure where various CLI tools like `aider` can be used as the Body via `settings.yaml`.
- **Dynamic Configuration**: Allows defining driver commands, arguments, and environment variables through configuration files without code modification.

#### Added
- **`Body` Class**: Established a new class dedicated to executing CLI tools.
- **Quota Management**: Added an automatic wait feature when Claude Code quota limits occur.
- **Concise Prompting**: Instructed the Brain to issue concise commands.
- **Real-time Mirroring**: Used `subprocess.Popen` to mirror execution output to the console in real-time.

#### Changed
- **Terminology**: Unified `Actor`/`CC` terms into `Body`.
- **Dependency**: Completely removed `pexpect` dependency.
- **Settings Structure**: Added a `body` section.

#### Technical Details
- **Environment Variables**: Supported `${VAR_NAME}` syntax.
- **Logging**: Clearly indicates the execution subject in log messages.

---

## [3.0.0] - 2024-12-18

### 🎉 Major Refactoring & Enhancements

#### Added
- **Stateless CLI Wrapper**: Introduced a stable communication method based on `subprocess`.
- **Schema Validation**: Added configuration file validation logic.
- **Google GenAI**: Migrated to the latest `google-genai` library.

---

## [2.0.0] - Previous Version

### Features
- Brain-based autonomous decision making.
- OODA Loop implementation.
- Multi-LLM support (Gemini, GPT, Claude).
