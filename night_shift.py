#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v4.1 - Sequential Task Execution)
Target: macOS M3 (Apple Silicon)
Version: 4.1.0

Core Features:
1. Brain Module (Director): Strategic decision making via CLI tools.
2. Hassan Module (Worker): Execution of commands via interchangeable CLI drivers.
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
import logging
from datetime import datetime, timedelta
import copy

# --- Configuration & Constants ---
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
SETTINGS_FILE = "settings.yaml"
BRAIN_WORKSPACE_DIR = os.path.join(".night_shift", "brain_hq")

# LLM Limits
MAX_CONTEXT_CHARS = 3000
MAX_HISTORY_CHARS = 4000
MAX_TOKENS = 1024
RATE_LIMIT_SLEEP = 2

# --- Utils ---
def setup_logging():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    log_file_path = LOG_FILE_TEMPLATE.format(timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"))
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s') # Keep console output clean
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger, log_file_path

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
    """The Intelligence Unit (Director). Decides what to do via CLI tools."""
    
    def __init__(self, settings):
        self.settings = settings
        self.brain_config = self.settings.get('brain', {})
        self.active_driver_name = self.brain_config.get('active_driver', 'claude')
        self.drivers = self.brain_config.get('drivers', {})
        
        # Setup Brain Workspace (Shadow Workspace)
        if not os.path.exists(BRAIN_WORKSPACE_DIR):
            os.makedirs(BRAIN_WORKSPACE_DIR, exist_ok=True)
        
        # Load driver config
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            logging.warning(f"⚠️ Brain Driver '{self.active_driver_name}' not found. Using default Claude config.")
            self.driver_config = {
                "command": "claude",
                "args": ["-p", "{prompt}"]
            }
            
        logging.info(f"🧠 Brain Initialized: [{self.active_driver_name.upper()}] CLI Mode")
        logging.info(f"🧠 Brain Workspace: {BRAIN_WORKSPACE_DIR}")

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def _log_brain_activity(self, message):
        """Logs detailed brain activity to a separate debug log file if needed."""
        brain_log_file = os.path.join(LOG_DIR, f"brain_log_{datetime.now().strftime('%Y%m%d')}.txt")
        try:
            with open(brain_log_file, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def _run_cli_command(self, prompt):
        """Executes the CLI command for the Brain."""
        base_cmd = self.driver_config.get("command", "claude")
        args_template = self.driver_config.get("args", [])
        
        cmd_list = [base_cmd]
        
        # Replace placeholders in args
        for arg in args_template:
            val = arg.replace("{prompt}", prompt)
            if val: 
                cmd_list.append(val)
        
        logging.info(f"🧠 Brain Thinking via {base_cmd} (in {BRAIN_WORKSPACE_DIR})...")
        
        try:
            # Brain runs in non-interactive mode, capturing stdout
            # Important: Run in the SHADOW WORKSPACE to keep sessions separate
            process = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                cwd=BRAIN_WORKSPACE_DIR, # Force Brain to work in its own room
                check=False 
            )
            
            if process.returncode != 0:
                error_msg = process.stderr.strip()
                logging.error(f"🧠 Brain CLI Error ({process.returncode}): {error_msg}")
                return f"MISSION_FAILED: Brain CLI Error - {error_msg}"
                
            return process.stdout.strip()
            
        except Exception as e:
            logging.error(f"🧠 Brain Execution Exception: {e}")
            return f"MISSION_FAILED: {e}"

    def think(self, current_task, total_goal_context, constraints, conversation_history, last_hassan_output):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        
        logging.info(f"\n--- 📥 INPUT TO BRAIN (HASSAN OUTPUT) ---\n{clean_output[:200]}...\n---------------------------------------")

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
        # Logging request (verbose)
        log_entry = f"\n{'='*80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'='*80}\n{prompt}\n"
        self._log_brain_activity(log_entry)

        response_text = self._run_cli_command(prompt)
            
        logging.info(f"--- 🧠 BRAIN RESPONSE ---\n{response_text}\n--- END RESPONSE ---")
            
        # Logging response (verbose)
        self._log_brain_activity(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-'*80}\n{response_text}\n")
        return response_text

class Hassan:
    """The Execution Unit (Worker/Slave). Abstraction for CLI tools."""
    
    def __init__(self, settings, mission_config):
        self.hassan_config = settings.get('body', {})
        if not self.hassan_config:
             self.hassan_config = settings.get('hassan', {})

        self.active_driver_name = self.hassan_config.get('active_driver', 'claude')
        self.drivers = self.hassan_config.get('drivers', {})
        self.mission_config = mission_config
        self.system_prompt_file = None
        
        # Load driver config
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            logging.warning(f"⚠️ Driver '{self.active_driver_name}' not found in settings. Using default Claude config.")
            self.driver_config = {
                "command": "claude",
                "args": ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}", "-c", "--dangerously-skip-permissions", "--allowedTools", "Write"],
                "env": {}
            }
            
        logging.info(f"🦾 Hassan Initialized: [{self.active_driver_name.upper()}] Driver")

    def prepare(self, current_goal_text):
        """Prepares resources like system prompt files with the CURRENT goal."""
        if current_goal_text:
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

        logging.info(f"\n--- 🚀 Running Hassan ({self.active_driver_name}) ---")
        logging.info(f"Command: {' '.join(cmd_list)}")
        logging.info(f"Query: {query}")
        logging.info("---")

        try:
            # Use Popen for real-time output mirroring
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, 
                text=True,
                cwd=self.mission_config.get('project_path', os.getcwd()),
                env=current_env,
                bufsize=1 
            )
            
            output_lines = []
            print("--- Hassan Output (Streaming) ---") 
            
            for line in process.stdout:
                print(line, end='') 
                output_lines.append(line)
            
            returncode = process.wait()
            full_output = "".join(output_lines).strip()
            
            print("-------------------------------") 

            if returncode != 0:
                return f"Hassan exited with error code {returncode}:\n{full_output}"
            return full_output

        except Exception as e:
            logging.error(f"ERROR running Hassan: {e}")
            return f"ERROR running Hassan: {e}"

class NightShiftAgent:
    def __init__(self, mission_path="mission.yaml"):
        # Setup Logging first
        self.logger, self.log_file_path = setup_logging()
        
        if not os.path.exists(mission_path):
            logging.error(f"❌ Mission file not found: {mission_path}")
            sys.exit(1)

        with open(mission_path, 'r', encoding='utf-8') as f:
            self.mission_config = yaml.safe_load(f)
        validate_mission_schema(self.mission_config)
        
        if not os.path.exists(SETTINGS_FILE):
            logging.warning(f"⚠️ {SETTINGS_FILE} not found. Using defaults.")
            self.settings = {}
        else:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = yaml.safe_load(f)

        # Initialize Modules
        self.brain = Brain(self.settings)
        self.hassan = Hassan(self.settings, self.mission_config)
        
        self.conversation_history = ""
        self.last_hassan_query = ""
        self.last_hassan_output = ""

    def _handle_quota_limit(self, error_message):
        try:
            # Case 1: "resets 10pm" (Claude)
            match_abs = re.search(r"resets\s+(\d+(?:am|pm))", error_message, re.IGNORECASE)
            # Case 2: "reset after 1h17m41s" or "after 5m" (Gemini)
            match_rel = re.search(r"after\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?", error_message, re.IGNORECASE)

            now = datetime.now()
            target = None

            if match_abs:
                time_str = match_abs.group(1)
                target = datetime.strptime(time_str, "%I%p").replace(year=now.year, month=now.month, day=now.day)
                if target < now: target += timedelta(days=1)
                target += timedelta(minutes=1) # Buffer
            elif match_rel and any(match_rel.groups()):
                h = int(match_rel.group(1) or 0)
                m = int(match_rel.group(2) or 0)
                s = int(match_rel.group(3) or 0)
                target = now + timedelta(hours=h, minutes=m, seconds=s + 30) # 30s buffer
            
            if not target:
                logging.warning("⚠️ Quota hit but time parse failed. Sleeping 1h.")
                time.sleep(3600); return

            sleep_sec = (target - now).total_seconds()
            if sleep_sec < 0: sleep_sec = 60 # Default fallback
            
            logging.warning(f"\n⏳ Quota limit detected. Sleeping until {target.strftime('%H:%M:%S')} ({sleep_sec/60:.1f}m)...")
            time.sleep(sleep_sec)
        except Exception as e:
            logging.error(f"Error in _handle_quota_limit: {e}")
            time.sleep(3600)

    def start(self):
        logging.info("🌙 Night Shift (v4.1) Starting...")
        
        raw_goals = self.mission_config.get('goal')
        goals = raw_goals if isinstance(raw_goals, list) else [raw_goals]
        constraints = self.mission_config.get('constraints', [])
        
        logging.info(f"📋 Mission loaded with {len(goals)} task(s).")
        
        try:
            for i, task in enumerate(goals, 1):
                logging.info(f"\n{'='*60}")
                logging.info(f"🚀 STARTING TASK {i}/{len(goals)}")
                logging.info(f"📄 Task: {task}")
                logging.info(f"{ '='*60}\n")
                
                self.hassan.prepare(current_goal_text=task)
                
                initial_query = f"Start Task {i}: {task}"
                hassan_output = self.hassan.run(initial_query)
                
                self.conversation_history += f"\n=== TASK {i} START ===\nDirector Init: {initial_query}\nHassan Output:\n{hassan_output}\n"
                self.last_hassan_query = initial_query
                self.last_hassan_output = hassan_output

                while True:
                    if "hit your limit" in self.last_hassan_output and "resets" in self.last_hassan_output:
                        self._handle_quota_limit(self.last_hassan_output)
                    
                    logging.info("\n🤔 Brain is thinking...")
                    next_action = self.brain.think(
                        task,
                        str(raw_goals),
                        constraints,
                        self.conversation_history,
                        self.last_hassan_output
                    )

                    logging.info(f"💡 Director (Brain): {next_action}")
                    self.conversation_history += f"\n--- 🧠 DIRECTOR (BRAIN) DECISION ---\n{next_action}\n----------------------------------\n"

                    # Check for Quota Limit in Brain's response
                    if "exhausted your capacity" in next_action or "quota" in next_action.lower() or "limit" in next_action.lower():
                        self._handle_quota_limit(next_action)
                        continue

                    if next_action == "MISSION_COMPLETED":
                        logging.info(f"✅ Task {i} Completed!"); break
                    if next_action.startswith("MISSION_FAILED"):
                        logging.error(f"❌ Task {i} Failed: {next_action}"); return 
                    if next_action == self.last_hassan_query:
                        logging.warning("⚠️ Loop detected. Skipping to next task?"); break 

                    hassan_output = self.hassan.run(next_action)
                    
                    self.conversation_history += f"\n--- 🦾 HASSAN ({self.hassan.active_driver_name.upper()}) OUTPUT ---\n{hassan_output}\n------------------------------\n"
                    
                    self.last_hassan_query = next_action
                    self.last_hassan_output = hassan_output
                    
                    time.sleep(RATE_LIMIT_SLEEP)

            logging.info(f"\n{'='*60}")
            logging.info("🏁 ALL TASKS COMPLETED. Requesting Final Commit & Push...")
            logging.info(f"{ '='*60}\n")
            self.hassan.run("Commit and push all changes now that all tasks are completed.")

        finally:
            self.hassan.cleanup()
            history_file = self.log_file_path.replace("night_shift_log", "night_shift_history")
            with open(history_file, "w", encoding="utf-8") as f:
                f.write(self.conversation_history)
            logging.info(f"📝 Full history saved: {history_file}")
            logging.info(f"📝 Runtime log saved: {self.log_file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain & Hassan")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()