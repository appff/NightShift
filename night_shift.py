#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v3.0 - Stateless CLI Wrapper)
Target: macOS M3 (Apple Silicon)
Version: 3.0.0

Core Features:
1. Brain Module (LLM) for autonomous decision making.
2. OODA Loop (Observe-Orient-Decide-Act) architecture.
3. Multi-LLM Support (Gemini, Claude, GPT).
4. Robust communication with Claude Code using non-interactive mode (`claude -p`).
"""

import subprocess
import sys
import time
import yaml
import re
import os
import argparse
from datetime import datetime
import json # For parsing Claude's JSON output if applicable

# --- Third-party LLM SDKs ---
try:
    import google.generativeai as genai
    from openai import OpenAI
    from anthropic import Anthropic
except ImportError:
    print("⚠️  Missing required LLM libraries. Please run: pip install google-generativeai openai anthropic")
    # We continue, assuming the user might fix it or use a mockup mode if we had one.
    # But practically, the Brain will fail.

# --- Configuration & Constants ---

# ANSI Escape Code Regex for cleaning output before analysis
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
REPORT_FILE = "morning_report.md"
SETTINGS_FILE = "settings.yaml"

class Brain:
    """The Intelligence Unit. Decides what to do based on the mission and current context."""
    
    def __init__(self, settings_path=SETTINGS_FILE):
        self.settings = self._load_settings(settings_path)
        self.model_type = self.settings.get('brain', {}).get('active_model', 'gemini')
        self.client = None
        self.model_name = ""
        self._setup_client()
        
        print(f"🧠 Brain Initialized: [{self.model_type.upper()}] Mode with model: {self.model_name}")

    def _load_settings(self, path):
        if not os.path.exists(path):
            print(f"⚠️  Settings file not found: {path}. Using defaults.")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _setup_client(self):
        brain_conf = self.settings.get('brain', {})
        
        if self.model_type == 'gemini':
            conf = brain_conf.get('gemini', {})
            api_key = conf.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("Gemini API Key is missing in settings.yaml or env vars.")
            genai.configure(api_key=api_key)
            self.model_name = conf.get('model', 'gemini-1.5-pro')
            
        elif self.model_type == 'gpt':
            conf = brain_conf.get('gpt', {})
            api_key = conf.get('api_key') or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API Key is missing.")
            self.client = OpenAI(api_key=api_key)
            self.model_name = conf.get('model', 'gpt-4o')
            
        elif self.model_type == 'claude':
            conf = brain_conf.get('claude', {})
            api_key = conf.get('api_key') or os.getenv("CLAUDE_API_KEY")
            if not api_key:
                raise ValueError("Anthropic API Key is missing.")
            self.client = Anthropic(api_key=api_key)
            self.model_name = conf.get('model', 'claude-3-opus-20240229')

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def think(self, mission_goal, constraints, conversation_history, last_claude_output):
        """
        Analyzes the situation and returns the next command for Claude Code.
        """
        clean_output = self.clean_ansi(last_claude_output)[-3000:] # Last 3000 chars context
        
        prompt = f"""
You are the "Director" of an autonomous coding session. 
Your "Actor" is a non-interactive CLI tool (Claude Code) which you invoke with `claude -p "YOUR_COMMAND_HERE" -c`.
Your goal is to guide the Actor to achieve the [MISSION GOAL].

[MISSION GOAL]
{mission_goal}

[CONSTRAINTS]
{constraints}

[CONVERSATION HISTORY]
{conversation_history[-4000:]}

[LAST ACTOR'S OUTPUT]
{clean_output}

[INSTRUCTIONS]
1. Analyze the [MISSION GOAL], [CONSTRAINTS], [CONVERSATION HISTORY], and [LAST ACTOR'S OUTPUT].
2. Determine the NEXT single, specific, and actionable command/query to send to Claude Code via the `-p` flag to move closer to the [MISSION GOAL].
3. If the Actor (Claude Code) requires a specific input (e.g., confirmation "y/n", a filename), provide that direct input.
4. If the Actor's output indicates the mission is complete, or you believe no further action is needed, reply with exactly: "MISSION_COMPLETED".
5. The command you output will be executed as `claude -p "YOUR_OUTPUT_HERE" -c`. Ensure it's a valid query for Claude Code.

[CRITICAL RULE]
- Your response MUST be ONLY the command/query string. No markdown, no explanations, no wrapping in quotes unless the command itself requires it.
- Do NOT repeat the exact same command if it was just executed and yielded no progress.
- Be concise and direct.
"""
        
        response_text = ""
        try:
            # For debugging, printing the prompt to console. For production, log to file.
            print("\n--- 🧠 PROMPT TO BRAIN ---")
            print(prompt)
            print("--- END PROMPT ---")

            if self.model_type == 'gemini':
                model = genai.GenerativeModel(self.model_name)
                resp = model.generate_content(prompt)
                response_text = resp.text.strip()
                
            elif self.model_type == 'gpt':
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": "You are a helpful AI Director. Respond ONLY with the command to execute."}, 
                              {"role": "user", "content": prompt}]
                )
                response_text = resp.choices[0].message.content.strip()
                
            elif self.model_type == 'claude':
                msg = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = msg.content[0].text.strip()
                
        except Exception as e:
            print(f"🧠 Brain Freeze (Error): {e}")
            return "MISSION_FAILED: LLM call failed."

        return response_text

class NightShiftAgent:
    def __init__(self, mission_path="mission.yaml"):
        if not os.path.exists(mission_path):
            print(f"❌ Mission file not found: {mission_path}")
            sys.exit(1)

        with open(mission_path, 'r', encoding='utf-8') as f:
            self.mission_config = yaml.safe_load(f)
        
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        
        self.log_file_path = LOG_FILE_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.brain = Brain()
        self.conversation_history = ""
        self.last_claude_query = ""
        self.last_claude_output = ""

    def _run_claude_command(self, query):
        if not query or query.strip() == "":
            # If Brain sends empty query, consider it mission failed or done.
            return "ERROR: Brain sent an empty query to Claude Code. Assuming mission failure."

        # Base command for Claude Code
        command = ["claude"]

        # Always include the system prompt for context
        if self.mission_config.get('goal'):
            command.extend(["--system-prompt", self.mission_config['goal']])

        # Add the actual query via -p
        command.extend(["-p", query])

        # Continue the most recent conversation
        command.append("-c")
        
        # Enable automated file modification
        command.append("--dangerously-skip-permissions")
        # Explicitly allow Write tool
        command.extend(["--allowedTools", "Write"])

        print(f"\n--- 🚀 Running Claude Code ---")
        print(f"Full Command: {' '.join(command)}")
        print(f"Query: {query}")
        print("---")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                cwd=self.mission_config.get('project_path', os.getcwd())
            )
            
            output = result.stdout.strip()
            error = result.stderr.strip()

            print(f"--- Claude Code Output ---")
            print(output)
            if error:
                print(f"--- Claude Code Error ---")
                print(error)
            print("---")

            if result.returncode != 0:
                # Claude Code can return non-zero for warnings, but we should capture if it's an actual error
                # For now, treat any non-zero as an error from the perspective of NightShift.
                return f"Claude Code exited with error code {result.returncode}:\n{output}\n{error}"
            
            return output

        except FileNotFoundError:
            return "ERROR: 'claude' command not found. Is Claude Code CLI installed and in PATH?"
        except Exception as e:
            return f"ERROR running Claude Code: {e}"

    def start(self):
        print("🌙 Night Shift (v3.0) Starting...")
        
        project_path = self.mission_config.get('project_path', os.getcwd())
        goal = self.mission_config.get('goal', 'No goal specified')
        constraints = self.mission_config.get('constraints', [])
        
        # Initial kickstart
        # Pass the main goal as --system-prompt once, then a generic start command
        # The _run_claude_command now always includes --system-prompt from mission_config['goal']
        initial_query = "Begin the mission. Analyze the current project based on the system prompt."
        claude_output = self._run_claude_command(initial_query)
        self.conversation_history += f"Director initial instruction: {initial_query}\nActor Output:\n{claude_output}\n"
        self.last_claude_query = initial_query
        self.last_claude_output = claude_output

        # while True:
        #     print("\n🤔 Brain is thinking...")
        #     next_action = self.brain.think(
        #         goal,
        #         constraints,
        #         self.conversation_history,
        #         self.last_claude_output
        #     )
        #
        #     print(f"💡 Brain decided: '{next_action}'")
        #
        #     if next_action == "MISSION_COMPLETED":
        #         print("🎉 Mission Accomplished. Exiting.")
        #         break
        #     
        #     if next_action.startswith("MISSION_FAILED"):
        #         print(f"❌ {next_action}. Exiting.")
        #         break
        #
        #     if next_action == self.last_claude_query:
        #         print(f"⚠️ Loop detected: Brain suggested '{next_action}' again without new output. Forcing break.")
        #         break
        #
        #     claude_output = self._run_claude_command(next_action)
        #     
        #     self.conversation_history += f"Director: {next_action}\nActor Output:\n{claude_output}\n"
        #     self.last_claude_query = next_action
        #     self.last_claude_output = claude_output
        #     
        #     # Simple rate limiting to avoid hammering LLM/Claude
        #     time.sleep(2) 

        print("\n👋 Night Shift Ended.")
        # Optionally, save final report or full history to log file.
        with open(self.log_file_path, "w", encoding="utf-8") as f:
            f.write(self.conversation_history)
        print(f"📝 Full conversation log saved to: {self.log_file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain-Powered Agent")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()