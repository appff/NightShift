# NightShift Architectural Review

## Scope
- Codebase under `nightshift/` and project documentation in `docs/`.
- Focus on orchestration flow, memory, validation, tool routing, and MCP integration.

## Architecture Overview
NightShift is a CLI-native agent orchestrator that coordinates three roles (Brain, Hassan, Critic) around a mission/task loop. The orchestrator (NightShiftAgent) is the central control point: it parses mission configuration, loads personas, builds a tool registry (local SmartTools + MCP tools), performs pre-flight/post-flight checks, and runs the Brain/Hassan loop per task. State, logs, summaries, and reflexion memory are persisted under `.night_shift/` and `logs/`.

## Core Components
- Orchestrator (`nightshift/orchestrator.py`): mission normalization, task loop, tool routing, persona selection, state persistence, and lock handling.
- Agents (`nightshift/agents.py`): Brain (planner/auditor), Hassan (executor), Critic (optional QA).
- Context/Persona (`nightshift/context.py`): loads persona markdown, regex-based persona rules, and message efficiency mode.
- Memory (`nightshift/memory.py` + `MemoryManager`): legacy memory plus Reflexion error/fix patterns.
- Validation (`nightshift/validation.py`): ConfidenceChecker (pre-flight), SelfCheckProtocol (post-flight).
- Tools (`nightshift/tools.py`): SmartTools for read/search/edit/run actions; MCP Manager for external tools (`nightshift/mcp_client.py`).

## Data Flow Summary
1. Mission is loaded and validated; tasks auto-normalized with ids/status.
2. Personas are selected (mission override or regex rules) and injected into agent prompts.
3. Token optimizer builds Layer 0 context (file tree + README) to reduce initial prompt size.
4. Pre-flight confidence check runs; Brain and Hassan are prepared with tool registry.
5. Brain produces JSON actions; orchestrator routes edits to SmartTools and `mcp_run` to MCP Manager.
6. Post-flight self-check validates evidence; task status/state updated; logs and summaries persisted.

## Strengths
- Clear separation of roles (Brain/Hassan/Critic) with an orchestrator enforcing evidence-based completion.
- Structured safety gates (pre-flight confidence + post-flight self-check) to reduce hallucination risk.
- Modular extension points: tool registry, MCP Manager, persona system, reflexion memory.
- Mission/task lifecycle is explicit and persisted (lock file, state file, logs, summaries).

## Risks / Gaps
- MCP health is only checked at startup; there is no retry/heartbeat or dynamic re-registration of tools if a server restarts.
- SelfCheckProtocol defaults to soft-pass on tests/requirements unless explicit signals exist, which can mask missing verification.
- ContextLoader silently falls back to a default persona when a persona file is missing, which can hide configuration errors.
- ConfidenceChecker duplication check uses naive glob matching on task keywords; in large repos this can be slow and noisy.
- Resume state is minimal (active task id + timestamp) with no mid-task checkpointing, so partial progress is lost on failure.

## Recommendations
- Add MCP health monitoring and periodic tool re-sync (or reconnection on failure) with clear error surfacing.
- Tighten SelfCheckProtocol for coding personas: require explicit test/evidence markers or annotated “not run” notes.
- Warn or fail fast when a requested persona file is missing to avoid silent behavioral drift.
- Make duplication scanning optional or rate-limited; consider restricting search to tracked directories.
- Enhance resume state with per-turn checkpoints or last-command replay information.

## Open Questions
- Should mission/task state support granular checkpoints for safe resumption mid-task?
- Do you want strict verification (fail if tests not run) for specific personas or task types?
- Should MCP connectivity be treated as mandatory when configured, or best-effort with warnings?
