#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v4.1 - Sequential Task Execution)
Target: macOS M3 (Apple Silicon)
Version: 4.1.0

Core Features:
1. Brain Module (LLM): Strategic decision making (Director).
2. Hassan Module (CLI Driver): Execution of commands via interchangeable drivers (Claude, Aider, etc.).
3. OODA Loop: Observe-Orient-Decide-Act loop for autonomous operation.
4. Stateless & Configurable: Fully driven by settings.yaml.
5. Sequential Tasking: Processes a list of goals one by one.
"""

import subprocess
import sys
import time
import yaml
import re
import os
import argparse
from datetime import datetime, timedelta
import copy

# --- Third-party LLM SDKs ---
from google import genai
from openai import OpenAI
from anthropic import Anthropic

# --- Configuration & Constants ---
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
SETTINGS_FILE = "settings.yaml"

# LLM Limits
MAX_CONTEXT_CHARS = 3000
MAX_HISTORY_CHARS = 4000
MAX_TOKENS = 1024
RATE_LIMIT_SLEEP = 2

# Defaults
DEFAULT_GEMINI_MODEL = 'gemini-1.5-pro-002'
DEFAULT_GPT_MODEL = 'gpt-4o'
DEFAULT_CLAUDE_MODEL = 'claude-3-5-sonnet-20240620'

# --- Utils ---
def validate_settings_schema(settings):
    """Simple validation for critical settings keys."""
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary")
    if 'brain' not in settings:
        raise ValueError("Missing 'brain' configuration")
    
def validate_mission_schema(mission_config):
    if 'goal' not in mission_config or not mission_config['goal']:
        raise ValueError("Mission must have a 'goal'")
    
    goal = mission_config['goal']
    if not isinstance(goal, (str, list)):
        raise ValueError("'goal' must be a string or a list of strings")
    
    if isinstance(goal, list):
        if not all(isinstance(item, str) for item in goal):
            raise ValueError("All items in 'goal' list must be strings")
        if len(goal) == 0:
            raise ValueError("'goal' list cannot be empty")

# --- Core Classes ---

class Brain:
    """The Intelligence Unit (Director). Decides what to do."""
    
    def __init__(self, settings):
        self.settings = settings
        self.model_type = self.settings.get('brain', {}).get('active_model', 'gemini')
        self.client = None
        self.model_name = ""
        self._setup_client()
        print(f"🧠 Brain Initialized: [{self.model_type.upper()}] Mode with model: {self.model_name}")

    def _setup_client(self):
        brain_config = self.settings.get('brain', {})
        if self.model_type == 'gemini':
            config = brain_config.get('gemini', {})
            api_key = config.get('api_key') or os.getenv("GEMINI_API_KEY")
            if not api_key: raise ValueError("Gemini API Key missing")
            self.client = genai.Client(api_key=api_key)
            self.model_name = config.get('model', DEFAULT_GEMINI_MODEL)
        elif self.model_type == 'gpt':
            config = brain_config.get('gpt', {})
            api_key = config.get('api_key') or os.getenv("OPENAI_API_KEY")
            if not api_key: raise ValueError("OpenAI API Key missing")
            self.client = OpenAI(api_key=api_key)
            self.model_name = config.get('model', DEFAULT_GPT_MODEL)
        elif self.model_type == 'claude':
            config = brain_config.get('claude', {})
            api_key = config.get('api_key') or os.getenv("CLAUDE_API_KEY")
            if not api_key: raise ValueError("Anthropic API Key missing")
            self.client = Anthropic(api_key=api_key)
            self.model_name = config.get('model', DEFAULT_CLAUDE_MODEL)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def _log_to_file(self, message):
        brain_log_file = os.path.join(LOG_DIR, f"brain_log_{datetime.now().strftime('%Y%m%d')}.txt")
        try:
            with open(brain_log_file, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def think(self, current_task, total_goal_context, constraints, conversation_history, last_hassan_output):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        
        # Log input for debugging
        print(f"\n--- 📥 INPUT TO BRAIN (HASSAN OUTPUT) ---\n{clean_output[:200]}...\n---------------------------------------")

        constraints_text = '\n'.join(constraints) if isinstance(constraints, list) else str(constraints)
        
        prompt = f"""
You are the "Director" of an autonomous coding session.
Your "Hassan" (Worker) is a CLI tool that executes your commands.

[CURRENT ACTIVE TASK]
{current_task}

[OVERALL MISSION CONTEXT]
{total_goal_context}

[CONSTRAINTS]
{constraints_text}

[CONVERSATION HISTORY]
{conversation_history[-MAX_HISTORY_CHARS:]}

[LAST HASSAN OUTPUT]
{clean_output}

[INSTRUCTIONS]
1. Focus ONLY on the [CURRENT ACTIVE TASK]. Hassan doesn't need to know about future tasks yet.
2. Analyze the [CONSTRAINTS] and [LAST HASSAN OUTPUT].
3. Determine the NEXT single, specific, and actionable command/query for Hassan to advance the current task.
4. **Handle Hassan's Prompts:**
   - If Hassan proposes a plan, evaluate it. If good, reply with "Proceed" or "Yes".
   - If Hassan offers choices, select the best one.
   - If Hassan needs confirmation ("y/n"), provide it.
5. If the [CURRENT ACTIVE TASK] is complete, reply exactly: "MISSION_COMPLETED".
6. Output ONLY the command string.

[CRITICAL RULE]
- **Keep your commands CONCISE (1-2 lines max).**
- Avoid sending long scripts. Rely on Hassan's internal capabilities.
- Do NOT repeat the exact same command if it failed.
"""
        # Logging request
        log_entry = f"\n{'='*80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'='*80}\n{prompt}\n"
        self._log_to_file(log_entry)

        try:
            if self.model_type == 'gemini':
                response = self.client.models.generate_content(model=self.model_name, contents=prompt)
                response_text = response.text.strip()
            elif self.model_type == 'gpt':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": "You are a Director. Respond ONLY with the command."}, {"role": "user", "content": prompt}]
                )
                response_text = response.choices[0].message.content.strip()
            elif self.model_type == 'claude':
                message = self.client.messages.create(
                    model=self.model_name, max_tokens=MAX_TOKENS, messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text.strip()
            
            print(f"--- 🧠 BRAIN RAW RESPONSE ---\n{response_text}\n--- END RAW RESPONSE ---")
            
            # Logging response
            self._log_to_file(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-'*80}\n{response_text}\n")
            return response_text

        except Exception as e:
            print(f"🧠 Brain Error: {e}")
            return f"MISSION_FAILED: {e}"

class Hassan:
    """The Execution Unit (Worker/Slave). Abstraction for CLI tools like Claude or Aider."""
    
    def __init__(self, settings, mission_config):
        self.hassan_config = settings.get('body', {}) # Still read 'body' from settings for compatibility
        if not self.hassan_config:
             self.hassan_config = settings.get('hassan', {}) # Try 'hassan' key too

        self.active_driver_name = self.hassan_config.get('active_driver', 'claude')
        self.drivers = self.hassan_config.get('drivers', {})
        self.mission_config = mission_config
        self.system_prompt_file = None
        
        # Load driver config
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            # Fallback default if not in settings.yaml (for compatibility)
            print(f"⚠️ Driver '{self.active_driver_name}' not found in settings. Using default Claude config.")
            self.driver_config = {
                "command": "claude",
                "args": ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}", "-c", "--dangerously-skip-permissions", "--allowedTools", "Write"],
                "env": {}
            }
            
        print(f"🦾 Hassan Initialized: [{self.active_driver_name.upper()}] Driver")

    def prepare(self, current_goal_text):
        """Prepares resources like system prompt files with the CURRENT goal."""
        if current_goal_text:
            # Use absolute path to ensure driver can find it regardless of cwd
            self.system_prompt_file = os.path.abspath(".night_shift_system_prompt.txt")
            with open(self.system_prompt_file, "w", encoding="utf-8") as f:
                f.write(current_goal_text)

    def cleanup(self):
        if self.system_prompt_file and os.path.exists(self.system_prompt_file):
            os.remove(self.system_prompt_file)

    def run(self, query):
        """Executes the driver command with the given query."""
        if not query: return "ERROR: Empty query."

        # 1. Build Command
        base_cmd = self.driver_config.get("command", "claude")
        args_template = self.driver_config.get("args", [])
        
        cmd_list = [base_cmd]
        
        # Replace placeholders in args
        for arg in args_template:
            val = arg.replace("{query}", query)
            if self.system_prompt_file:
                val = val.replace("{system_prompt_file}", self.system_prompt_file)
            else:
                val = val.replace("{system_prompt_file}", "") 
            
            if val: 
                cmd_list.append(val)

        # 2. Build Environment
        env_config = self.driver_config.get("env", {})
        current_env = os.environ.copy()
        
        for key, value in env_config.items():
            if isinstance(value, str) and value.startswith("${{") and value.endswith("}}"):
                var_name = value[2:-1]
                resolved_value = os.getenv(var_name, "")
                current_env[key] = resolved_value
            else:
                current_env[key] = str(value)

        print(f"\n--- 🚀 Running Hassan ({self.active_driver_name}) ---")
        print(f"Command: {' '.join(cmd_list)}")
        print(f"Query: {query}")
        print("---")

        try:
            # Use Popen for real-time output mirroring
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout
                text=True,
                cwd=self.mission_config.get('project_path', os.getcwd()),
                env=current_env,
                bufsize=1 # Line buffered
            )
            
            output_lines = []
            print("--- Hassan Output (Streaming) ---")
            
            # Read line by line
            for line in process.stdout:
                print(line, end='') # Mirror to console immediately
                output_lines.append(line)
            
            # Wait for process to finish
            returncode = process.wait()
            full_output = "".join(output_lines).strip()
            
            print("-------------------------------")

            if returncode != 0:
                return f"Hassan exited with error code {returncode}:\n{full_output}"
            return full_output

        except Exception as e:
            return f"ERROR running Hassan: {e}"

class NightShiftAgent:
    def __init__(self, mission_path="mission.yaml"):
        if not os.path.exists(mission_path):
            print(f"❌ Mission file not found: {mission_path}")
            sys.exit(1)

        with open(mission_path, 'r', encoding='utf-8') as f:
            self.mission_config = yaml.safe_load(f)
        validate_mission_schema(self.mission_config)
        
        if not os.path.exists(SETTINGS_FILE):
            print(f"⚠️ {SETTINGS_FILE} not found. Using defaults.")
            self.settings = {}
        else:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = yaml.safe_load(f)

        if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
        
        self.log_file_path = LOG_FILE_TEMPLATE.format(timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"))
        
        # Initialize Modules
        self.brain = Brain(self.settings)
        self.hassan = Hassan(self.settings, self.mission_config)
        
        self.conversation_history = ""
        self.last_hassan_query = ""
        self.last_hassan_output = ""

    def _handle_quota_limit(self, error_message):
        try:
            match = re.search(r"resets\s+(\d+(?:am|pm))", error_message, re.IGNORECASE)
            if not match:
                print("⚠️ Quota hit but time parse failed. Sleeping 1h.")
                time.sleep(3600); return

            time_str = match.group(1)
            now = datetime.now()
            target = datetime.strptime(time_str, "%I%p").replace(year=now.year, month=now.month, day=now.day)
            if target < now: target += timedelta(days=1)
            target += timedelta(minutes=5) # Buffer
            
            sleep_sec = (target - now).total_seconds()
            print(f"\n⏳ Quota limit. Sleeping until {target} ({sleep_sec/60:.1f}m)...")
            time.sleep(sleep_sec)
        except Exception:
            time.sleep(3600)

    def start(self):
        print("🌙 Night Shift (v4.1) Starting...")
        
        # Determine Goals (List or String)
        raw_goals = self.mission_config.get('goal')
        goals = raw_goals if isinstance(raw_goals, list) else [raw_goals]
        constraints = self.mission_config.get('constraints', [])
        
        print(f"📋 Mission loaded with {len(goals)} task(s).")
        
        try:
            for i, task in enumerate(goals, 1):
                print(f"\n{'='*60}")
                print(f"🚀 STARTING TASK {i}/{len(goals)}")
                print(f"📄 Task: {task}")
                print(f"{ '='*60}\n")
                
                # Update System Prompt for CURRENT Task
                self.hassan.prepare(current_goal_text=task)
                
                # Kickstart this specific task
                initial_query = f"Start Task {i}: {task}"
                hassan_output = self.hassan.run(initial_query)
                
                self.conversation_history += f"\n=== TASK {i} START ===\nDirector Init: {initial_query}\nHassan Output:\n{hassan_output}\n"
                self.last_hassan_query = initial_query
                self.last_hassan_output = hassan_output

                while True:
                    # Quota Check
                    if "hit your limit" in self.last_hassan_output and "resets" in self.last_hassan_output:
                        self._handle_quota_limit(self.last_hassan_output)
                    
                    print("\n🤔 Brain is thinking...")
                    next_action = self.brain.think(
                        task, # Current Task
                        str(raw_goals), # Total Context (String representation of full list)
                        constraints,
                        self.conversation_history,
                        self.last_hassan_output
                    )

                    print(f"💡 Director (Brain): {next_action}")
                    self.conversation_history += f"\n--- 🧠 DIRECTOR (BRAIN) DECISION ---\n{next_action}\n----------------------------------\n"

                    if next_action == "MISSION_COMPLETED":
                        print(f"✅ Task {i} Completed!"); break
                    if next_action.startswith("MISSION_FAILED"):
                        print(f"❌ Task {i} Failed: {next_action}"); return # Exit all on failure? Or continue? Let's stop.
                    if next_action == self.last_hassan_query:
                        print("⚠️ Loop detected. Skipping to next task?"); break # Or stop? Let's break task loop.

                    hassan_output = self.hassan.run(next_action)
                    
                    self.conversation_history += f"\n--- 🦾 HASSAN ({self.hassan.active_driver_name.upper()}) OUTPUT ---\n{hassan_output}\n------------------------------\n"
                    
                    self.last_hassan_query = next_action
                    self.last_hassan_output = hassan_output
                    
                    time.sleep(RATE_LIMIT_SLEEP)

        finally:
            self.hassan.cleanup()
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.write(self.conversation_history)
            print(f"📝 Log saved: {self.log_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain & Hassan")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()
