# Quality Gates: Ensuring True Completion

A common challenge in LLM-based autonomous agents is "hallucinated completion," where an agent reports a task is finished without providing sufficient evidence or meeting all implicit requirements. NightShift solves this with a multi-layered validation process called **Quality Gates**.

This document explains why you might see a few extra interactions between the Brain and Hassan even after the Brain initially reports `{"status": "completed"}`. This is not an inefficiency; it is a critical, token-efficient quality assurance mechanism.

## The Three-Step Completion Process

NightShift doesn't blindly accept the first "done" signal from the Brain. It follows a rigorous three-step process:

### Step 1: Brain's Initial Assessment (Subjective Completion)
- **What Happens**: The Brain analyzes the output from Hassan (the worker) and compares it to the task description.
- **Signal**: If it believes the task is complete, it returns `{"status": "completed"}`.
- **Limitation**: This is a subjective judgment from the LLM, which can sometimes be mistaken or overlook details.

### Step 2: `SelfCheckProtocol` (Objective Verification)
- **What Happens**: This is the most critical gate. The Orchestrator intercepts the Brain's `completed` signal and triggers the `SelfCheckProtocol` *before* finalizing the task.
- **Logic**: This protocol acts as an automated, evidence-based code reviewer. It mechanically checks the execution log against a set of persona-aware rules.
    
    **Updated "Soft Pass" Strategy (v5.1+):**
    To prevent infinite loops on tasks where verification is ambiguous, the protocol now defaults to **PASS** unless it finds **explicit evidence of failure**.
    
    - **Is it a coding task?** 
        - Default: **PASS**.
        - Fail Condition: Explicit keywords like "failed", "error", or "traceback" in the logs.
    - **Is the persona's core duty met?** (Strict checks for specific roles)
        - `technical-writer`: Must produce documentation ("README", "guide", "doc").
        - `deep-research-agent`: Must cite sources ("http", "source:").
    - **Was there evidence of work?** 
        - Must show file changes or substantial execution logs (`assumptions_verified`, `evidence_provided`).

- **Signal**:
    - **If Passed**: The protocol confirms the completion, and the Orchestrator proceeds to the final step.
    - **If Failed**: The protocol generates a **new corrective command** (e.g., `"Self-Check Failed. Missing evidence for: ['tests_passed']. Please verify and provide evidence."`). This command is sent back to Hassan, forcing it to address the specific quality gap. This is why you see another Brain-Hassan cycle.
    - **Safety Net**: To prevent infinite loops, retries are limited to 2 attempts. If it still fails, the system forces completion with a warning.

### Step 3: Final Confirmation (Housekeeping)
- **What Happens**: Once the `SelfCheckProtocol` is satisfied, the Brain gives one final look to ensure no loose ends remain (e.g., temporary files, final status checks).
- **Signal**: The final `MISSION_COMPLETED` is issued, and the task loop terminates.

## Why This is More Token-Efficient

While these extra validation steps consume a few hundred tokens, they prevent catastrophic failures that would waste tens of thousands of tokens.

## MCP-Enhanced Verification (v5.5+)

With the introduction of **Model Context Protocol (MCP)** support, quality gates have become even more robust:

- **Sequential Thinking**: The Brain can now use structured reasoning to "double-check" its own logic before submitting a task. This reduces the need for Orchestrator-level corrections.
- **Serena Memory**: Insights from previous tasks are stored and retrieved to ensure cross-task consistency, preventing regressions.
- **Symbolic Analysis**: Using Serena's LSP tools, the Brain can verify that code changes are semantically correct, not just syntactically valid.

- **Prevents Costly Rework**: It's far cheaper to run a 500-token validation cycle than to re-run an entire 20,000-token task from scratch because the first attempt was subtly flawed.
- **Ensures High-Quality Output**: It guarantees that the final output is not just complete, but correct and aligned with the persona's role.
- **Builds Trust**: This systematic verification makes the agent's output more reliable and trustworthy.

In summary, the "extra turns" are the core of NightShift's reliability, transforming it from a simple command-executor into a true quality-aware autonomous agent.