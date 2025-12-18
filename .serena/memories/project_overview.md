# Night Shift Project Overview

## Purpose
Night Shift is an **Autonomous AI Agent Orchestrator** that acts as a "Brain" for directing AI coding tools like Claude Code. It uses an OODA Loop (Observe-Orient-Decide-Act) to autonomously guide AI coding tools toward completing user-defined goals.

## Key Features
- **The Brain**: Uses LLMs (Gemini, GPT, Claude) to make decisions about what actions to take
- **OODA Loop**: Continuously observes, orients, decides, and acts to complete missions
- **Natural Language Missions**: Users define goals in natural language rather than rigid command lists
- **Safety Constraints**: Supports defining constraints to prevent unsafe operations
- **Multi-LLM Support**: Can switch between Gemini, Claude, and GPT via configuration

## Tech Stack
- **Language**: Python 3
- **Dependencies**:
  - `pexpect`: For process interaction
  - `pyyaml`: For YAML configuration parsing
  - `google-generativeai`: Gemini API client
  - `openai`: OpenAI GPT API client
  - `anthropic`: Claude API client

## Architecture
The project consists of two main classes:
1. **Brain**: The intelligence unit that decides what commands to send to Claude Code
2. **NightShiftAgent**: The orchestrator that manages the mission lifecycle and executes commands

## File Structure
- `night_shift.py`: Main executable script
- `settings.yaml`: LLM configuration and API keys
- `mission.yaml`: Mission goals and constraints
- `logs/`: Execution logs directory
- `docs/`: Documentation
- `requirements.txt`: Python dependencies
