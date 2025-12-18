#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v4.0 - Brain & Body Architecture)
Target: macOS M3 (Apple Silicon)
Version: 4.0.0

Core Features:
1. Brain Module (LLM): Strategic decision making (Director).
2. Body Module (CLI Driver): Execution of commands via interchangeable drivers (Claude, Aider, etc.).
3. OODA Loop: Observe-Orient-Decide-Act loop for autonomous operation.
4. Stateless & Configurable: Fully driven by settings.yaml.
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

# Default model names
# 유지보수성 개선: 모델명을 한 곳에서 관리하여 변경 시 수정 지점을 명확히 함
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
    # Body config is optional but recommended for v4.0 features
    
def validate_mission_schema(mission_config):
    if 'goal' not in mission_config or not mission_config['goal']:
        raise ValueError("Mission must have a 'goal'")

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

    def think(self, mission_goal, constraints, conversation_history, last_body_output):
        clean_output = self.clean_ansi(last_body_output)[-MAX_CONTEXT_CHARS:]
        
        # Log input for debugging
        print(f"\n--- 📥 INPUT TO BRAIN (BODY OUTPUT) ---\n{clean_output[:200]}...\n---------------------------------------")

        constraints_text = '\n'.join(constraints) if isinstance(constraints, list) else str(constraints)
        
        prompt = f"""
You are the "Director" of an autonomous coding session.
Your "Body" (Actor) is a CLI tool that executes your commands.
Your goal is to guide the Body to achieve the [MISSION GOAL].

[MISSION GOAL]
{mission_goal}

[CONSTRAINTS]
{constraints_text}

[CONVERSATION HISTORY]
{conversation_history[-MAX_HISTORY_CHARS:]}

[LAST BODY OUTPUT]
{clean_output}

[INSTRUCTIONS]
1. Analyze the [MISSION GOAL], [CONSTRAINTS], and [LAST BODY OUTPUT].
2. Determine the NEXT single, specific, and actionable command/query for the Body.
3. **Handle Body's Prompts:**
   - If the Body proposes a plan, evaluate it. If good, reply with "Proceed" or "Yes".
   - If the Body offers choices, select the best one.
   - If the Body needs confirmation ("y/n"), provide it.
4. If the mission is complete, reply exactly: "MISSION_COMPLETED".
5. Output ONLY the command string.

[CRITICAL RULE]
- **Keep your commands CONCISE (1-2 lines max).**
- Avoid sending long scripts. Rely on the Body's internal capabilities.
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

class Body:
    """The Execution Unit (Actor). Abstraction for CLI tools like Claude or Aider."""
    
    def __init__(self, settings, mission_config):
        self.body_config = settings.get('body', {})
        self.active_driver_name = self.body_config.get('active_driver', 'claude')
        self.drivers = self.body_config.get('drivers', {})
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
            
        print(f"🦾 Body Initialized: [{self.active_driver_name.upper()}] Driver")

    def prepare(self):
        """Prepares resources like system prompt files."""
        goal = self.mission_config.get('goal', '')
        if goal:
            self.system_prompt_file = ".night_shift_system_prompt.txt"
            with open(self.system_prompt_file, "w", encoding="utf-8") as f:
                f.write(goal)

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
                # If no file, and arg requires it, we might need to skip or handle empty.
                # For now, just replace with empty string or handle logic
                val = val.replace("{system_prompt_file}", "") 
            
            # Simple check to avoid adding empty args if replacement resulted in empty (unless intended)
            # But arguments like "-p" must be kept. 
            # Ideally, we should filter pairs, but list-based replacement is simpler.
            if val: 
                cmd_list.append(val)

        # 2. Build Environment
        env_config = self.driver_config.get("env", {})
        current_env = os.environ.copy()
        
        for key, value in env_config.items():
            # Support ${VAR} syntax for referencing existing env vars
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                resolved_value = os.getenv(var_name, "")
                current_env[key] = resolved_value
            else:
                current_env[key] = str(value)

        print(f"\n--- 🚀 Running Body ({self.active_driver_name}) ---")
        print(f"Command: {' '.join(cmd_list)}")
        print(f"Query: {query}")
        print("---")

        try:
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                check=False,
                cwd=self.mission_config.get('project_path', os.getcwd()),
                env=current_env
            )
            output = result.stdout.strip()
            error = result.stderr.strip()

            print(f"--- Body Output ---")
            print(output)
            if error:
                print(f"--- Body Error ---")
                print(error)
            print("---")

            if result.returncode != 0:
                return f"Body exited with error code {result.returncode}:\n{output}\n{error}"
            return output

        except Exception as e:
            return f"ERROR running Body: {e}"

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
        self.body = Body(self.settings, self.mission_config)
        
        self.conversation_history = ""
        self.last_body_query = ""
        self.last_body_output = ""

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
        print("🌙 Night Shift (v4.0) Starting...")
        
        self.body.prepare()
        
        try:
            # Initial Kickstart
            initial_query = "Begin the mission. Analyze the project based on the system prompt."
            body_output = self.body.run(initial_query)
            
            self.conversation_history += f"Director Init: {initial_query}\nBody Output:\n{body_output}\n"
            self.last_body_query = initial_query
            self.last_body_output = body_output

            while True:
                # Quota Check
                if "hit your limit" in self.last_body_output and "resets" in self.last_body_output:
                    self._handle_quota_limit(self.last_body_output)
                    # Retry logic implied by loop continuation (Brain sees error and retries)
                
                print("\n🤔 Brain is thinking...")
                next_action = self.brain.think(
                    self.mission_config.get('goal', ''),
                    self.mission_config.get('constraints', []),
                    self.conversation_history,
                    self.last_body_output
                )

                print(f"💡 Director (Brain): {next_action}")
                self.conversation_history += f"\n--- 🧠 DIRECTOR (BRAIN) DECISION ---\n{next_action}\n----------------------------------\n"

                if next_action == "MISSION_COMPLETED":
                    print("🎉 Mission Accomplished."); break
                if next_action.startswith("MISSION_FAILED"):
                    print(f"❌ {next_action}"); break
                if next_action == self.last_body_query:
                    print("⚠️ Loop detected. Breaking."); break

                body_output = self.body.run(next_action)
                
                self.conversation_history += f"\n--- 🦾 BODY ({self.body.active_driver_name.upper()}) OUTPUT ---\n{body_output}\n------------------------------\n"
                
                self.last_body_query = next_action
                self.last_body_output = body_output
                
                time.sleep(RATE_LIMIT_SLEEP)

        finally:
            self.body.cleanup()
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.write(self.conversation_history)
            print(f"📝 Log saved: {self.log_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain & Body")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()
