# 🌙 NightShift Roadmap (SuperClaude Inspired)

This roadmap outlines the evolution of NightShift into a more resilient, evidence-based, and self-learning autonomous agent orchestrator.

## Phase 1: Learning & Context Foundation (Current Priority)
Focus on learning from mistakes and structuring contexts for better LLM performance.

- [x] **1. Reflexion Memory System (`reflexion.jsonl`)**
    - [x] Implement structured error logging (Signature, Root Cause, Fix).
    - [x] Mechanism to fuzzy-match current errors against past solutions.
    - [x] Auto-apply "Adopted" solutions without rethinking.
- [x] **2. Markdown-based Persona Context (Context-Oriented Config)**
    - [x] Extract persona definitions from `settings.yaml` to `personas/*.md`.
    - [x] Support detailed markdown formatting for architect, troubleshoot, and other personas.
    - [x] Implement a context loader to inject these files into LLM prompts.

## Phase 2: Pre-Flight & Post-Flight Validation
Focus on preventing failure and ensuring quality evidence.

- [x] **3. Confidence Check System (Pre-Flight)**
    - [x] Implement `ConfidenceChecker` class.
    - [x] Check 1: Duplication Check (grep/glob).
    - [x] Check 2: Documentation/Reference Check.
    - [x] Logic: If confidence < 0.7, trigger research or ask user.
- [x] **4. Self-Check Protocol (Post-Flight)**
    - [x] Enforce "The 4 Questions" before Hassan reports task completion.
    - [x] Require evidence (test logs, file diffs) for every "DONE" status.

## Phase 3: Project Scalability & Efficiency
Focus on handling large-scale projects with minimal token waste.

- [x] **5. Token Optimization (Bootstrap & Progressive Loading)**
    - [x] Layer 0 Bootstrap: Initially load only file tree and README.
    - [x] Progressive Context: Selectively load only relevant file contents based on task intent.
- [x] **6. Intent-based Resource Allocation**
    - [x] Classify task complexity (Simple fix vs. Architecture change).
    - [x] Adjust agent depth and token budget based on classification.

## Future Extended Capabilities (In the Future)
- [ ] **MCP (Model Context Protocol) Integration**
    - [ ] Tavily MCP (Web Search).
    - [ ] Context7 MCP (Official Framework Docs).
    - [ ] Serena/Mindbase MCP (Semantic Code Memory).
