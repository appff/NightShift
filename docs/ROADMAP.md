# Roadmap

This document outlines the planned architectural improvements for Night Shift.

## 🚀 Upcoming Improvements

### 1. Hybrid Observation (Direct Brain "Read" Tools)
**Goal**: Reduce mission turn count by allowing the Brain to observe the project state directly without delegating read-only tasks to Hassan.

- **Implementation**: 
  - Enhance `Brain.think` to support an internal "observation" phase.
  - Automatically identify read-only commands (e.g., `ls`, `grep`, `read_file`) in the Brain's output.
  - Execute these commands locally and immediately re-feed the results into the Brain's context.
  - Reserve Hassan only for state-changing operations (Writes, Complex Executes).
- **Status**: Implementation in progress.

### 2. Semantic Memory (RAG-based Lessons Learned)
**Goal**: Scale the memory system beyond a single Markdown file to handle hundreds of missions without context overflow.

- **Implementation**:
  - Replace full-file memory loading with a retrieval mechanism.
  - Store "Lessons Learned" with metadata (task type, tools used).
  - Use a lightweight semantic search (or a "Memory Search" turn) to find the top 3 most relevant insights for the current mission.
- **Status**: Implementation in progress.

### 3. Multi-Agent Swarm & Conflict Resolution
**Goal**: Support complex parallel tasks that modify the same codebase.

- **Implementation**:
  - Introduce an "Architect" persona that runs after parallel tasks.
  - Architect reviews git diffs from all worktrees.
  - Automates resolution of merge conflicts between task branches.
- **Status**: Planned.

## ✅ Completed Improvements

### v4.4.2: Robustness and Structured Reasoning
- **JSON Output**: Forced Brain to use JSON for unambiguous state transitions.
- **Tail-based Filtering**: Stripped Codex execution noise to save tokens.
- **Scope Enforcement**: Instructed Brain to ignore optional worker expansions.
- **Auth Fix**: Inherited system `HOME` for stable CLI authentication.
