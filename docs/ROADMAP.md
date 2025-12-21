# 🗺️ Night Shift Roadmap & Evolution Ideas

This document outlines potential future upgrades and "fancy" features to evolve Night Shift from a powerful orchestrator into a legendary agentic framework.

---

## 🛡️ 1. The "Critic" Module (Dual-Brain Verification)
Status: Implemented.
- **Concept**: Add a third entity called **The Critic (or "The QA")**.
- **How it works**: Once Hassan completes a task, the Critic (using a different model, e.g., Gemini if Brain is Claude) reviews the output and logs. If unsatisfied, it sends Hassan back into the OODA loop with specific feedback.
- **Goal**: Significantly reduce hallucinations and edge-case errors.

## 📚 2. "Memories of the Night" (Persistent Memory)
Status: Implemented (Markdown-based memory file).
- **Concept**: A long-term knowledge base that survives across different projects.
- **How it works**: Implement a local Vector DB (like ChromaDB) or a Markdown-based "Knowledge Vault." After every mission, Night Shift stores a "Post-Mortem" summary of lessons learned.
- **Goal**: The Brain becomes an expert on the user's specific coding style, preferred libraries, and environment quirks over time.

## ⚡ 3. "The Squad" (Parallel Multi-Agents)
Status: Implemented (isolated task workspaces).
- **Concept**: Parallel execution for independent task goals.
- **How it works**: If a mission has multiple independent goals, Night Shift spawns multiple Hassans in isolated environments to work simultaneously.
- **Goal**: Massive performance boost for large-scale refactoring.

## ⏪ 4. "Safety Net" (Snapshot & Rollback)
Status: Implemented (backup branch + auto rollback with stash).
- **Concept**: Automated Git-based checkpoints for every task.
- **How it works**: Before starting a task, Night Shift creates a temporary branch or git stash. If the task fails or the Critic rejects the work, it performs an automatic rollback.
- **Goal**: Guaranteed "no-break" autonomous coding sessions.

## 🎭 5. Dynamic Specialist Personas (Synchronized Identity)
Status: Implemented (persona injection).
- **Concept**: Align both the Brain (Director) and Hassan (Worker) under a single specialized persona (e.g., Architect, Troubleshooter, Documenter) to ensure consistent thinking and execution.
- **Implementation Strategy (Persona Injection)**:
    - **Shared Guidelines**: Define expert personas in `settings.yaml`.
    - **Brain Sync**: The persona is injected into the Brain's prompt, influencing its strategic commands.
    - **Hassan Sync**: The same persona is appended to Hassan's `.night_shift_system_prompt.txt`. This ensures the executor (e.g., Claude Code) adopts the same identity as the strategist.
- **Example (Troubleshooter Mode)**:
    - **Brain**: "Don't just fix code; analyze logs and find the root cause first."
    - **Hassan**: "I am a Troubleshooter. I will explain the logic behind every fix and output relevant tracebacks for verification."
- **Goal**: Achieve "SuperClaude"-tier precision by ensuring the entire agentic squad shares the same professional mental model.

---

*Got a new idea? Feel free to add it to the list!*
