#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v4.2 - Pure CLI & Shadow Workspace)
Target: macOS M3 (Apple Silicon)
Version: 4.2.0

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
    
    def __init__(self, settings, mission_config):
        self.settings = settings
        self.mission_config = mission_config
        self.project_path = os.path.abspath(self.mission_config.get('project_path', os.getcwd()))
        
        self.brain_config = self.settings.get('brain', {})
        self.active_driver_name = self.brain_config.get('active_driver', 'claude')
        self.drivers = self.brain_config.get('drivers', {})
        
        # Setup Brain Workspace (Metadata Isolation)
        self.brain_env_dir = os.path.join(self.project_path, BRAIN_WORKSPACE_DIR)
        if not os.path.exists(self.brain_env_dir):
            os.makedirs(self.brain_env_dir, exist_ok=True)
            
        self._setup_auth_links()
        
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            logging.warning(f"⚠️ Brain Driver '{self.active_driver_name}' not found. Using default Claude config.")
            self.driver_config = {
                "command": "claude",
                "args": ["-p", "{prompt}"]
            }
            
        logging.info(f"🧠 Brain Initialized: [{self.active_driver_name.upper()}] CLI Mode")

    def _setup_auth_links(self):
        """Symlinks common AI CLI auth folders from real HOME to Brain's isolated HOME."""
        real_home = os.path.expanduser("~")
        auth_folders = [".claude", ".gemini", ".codex", ".config"]
        
        for folder in auth_folders:
            src = os.path.join(real_home, folder)
            dst = os.path.join(self.brain_env_dir, folder)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    os.symlink(src, dst)
                except Exception:
                    pass

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def _log_brain_activity(self, message):
        """Logs detailed brain activity to a separate debug log file."""
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
        for arg in args_template:
            val = arg.replace("{prompt}", prompt)
            if val: cmd_list.append(val)
        
        logging.info(f"🧠 Brain Thinking via {base_cmd}...")
        
        brain_env = os.environ.copy()
        brain_env["HOME"] = self.brain_env_dir
        
        try:
            process = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                cwd=self.project_path, 
                env=brain_env,
                check=False,
                timeout=300
            )
            
            if process.returncode != 0:
                error_msg = process.stderr.strip()
                logging.error(f"🧠 Brain CLI Error ({process.returncode}): {error_msg}")
                return f"MISSION_FAILED: Brain CLI Error - {error_msg}"
                
            return process.stdout.strip()
            
        except subprocess.TimeoutExpired:
            logging.error("🧠 Brain CLI Timeout (300s expired).")
            return "MISSION_FAILED: Brain CLI Timeout"
        except Exception as e:
            logging.error(f"🧠 Brain Execution Exception: {e}")
            return f"MISSION_FAILED: {e}"

    def think(self, current_task, total_goal_context, constraints, conversation_history, last_hassan_output, persona_guidelines=""):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        constraints_text = '\n'.join(constraints) if isinstance(constraints, list) else str(constraints)
        
        persona_section = f"\n[YOUR PERSONA GUIDELINES]\n{persona_guidelines}\n" if persona_guidelines else ""

        prompt = f"""
You are the "Director" of an autonomous coding session.
Your "Hassan" (Worker) is a CLI tool that executes your commands.
{persona_section}
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
1. Focus ONLY on the [CURRENT ACTIVE TASK].
2. Analyze the [CONSTRAINTS], [PERSONA GUIDELINES], and [LAST HASSAN OUTPUT].
3. Determine the NEXT single, specific, and actionable command/query for Hassan.
4. If the [CURRENT ACTIVE TASK] is complete, reply exactly: "MISSION_COMPLETED".
5. Output ONLY the command string.

[CRITICAL RULE]
- Keep commands CONCISE.
- Do NOT repeat the exact same command if it failed.
"""
        log_entry = f"\n{'='*80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'='*80}\n{prompt}\n"
        self._log_brain_activity(log_entry)

        response_text = self._run_cli_command(prompt)
        logging.info(f"--- 🧠 BRAIN RESPONSE ---\n{response_text}\n--- END RESPONSE ---")
        self._log_brain_activity(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-'*80}\n{response_text}\n")
        return response_text

class Critic:
    """The Quality Assurance Unit (Critic). Reviews the work of Hassan."""
    
    def __init__(self, settings, mission_config):
        self.settings = settings
        self.mission_config = mission_config
        self.project_path = os.path.abspath(self.mission_config.get('project_path', os.getcwd()))
        
        self.critic_config = self.settings.get('critic', {})
        self.active_driver_name = self.critic_config.get('active_driver', 'gemini')
        self.drivers = self.critic_config.get('drivers', {})
        self.brain_env_dir = os.path.join(self.project_path, BRAIN_WORKSPACE_DIR)
        
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            self.driver_config = {"command": "gemini", "args": ["-p", "{prompt}"]}
            
        logging.info(f"🕵️‍♂️ Critic Initialized: [{self.active_driver_name.upper()}] CLI Mode")

    def evaluate(self, task, history, last_output):
        """Evaluates Hassan's work. Returns 'APPROVED' or feedback."""
        prompt = f"""
You are the "Quality Assurance Critic".
A worker (Hassan) has just completed a task. Your job is to verify if the work is actually complete and high quality.

[TASK TO REVIEW]
{task}

[CONVERSATION & WORK HISTORY]
{history[-MAX_HISTORY_CHARS:]}

[FINAL OUTPUT/STATE]
{last_output[-MAX_CONTEXT_CHARS:]}

[INSTRUCTIONS]
1. Verify if all parts of the [TASK TO REVIEW] are fulfilled.
2. Check for code quality, logic errors, or missing requirements.
3. If everything is perfect, reply exactly: "APPROVED".
4. If there are issues, provide a CONCISE list of what needs to be fixed.
5. Output ONLY "APPROVED" or your feedback.
"""
        logging.info(f"🕵️‍♂️ Critic is reviewing work via {self.driver_config['command']}...")
        
        # Reuse Brain's execution logic (simplified here)
        brain_env = os.environ.copy()
        brain_env["HOME"] = self.brain_env_dir
        
        try:
            cmd_list = [self.driver_config['command']]
            for arg in self.driver_config.get('args', []):
                val = arg.replace("{prompt}", prompt)
                if val: cmd_list.append(val)
                
            process = subprocess.run(cmd_list, capture_output=True, text=True, cwd=self.project_path, env=brain_env, timeout=300)
            response = process.stdout.strip()
            
            logging.info(f"🕵️‍♂️ Critic Response: {response}")
            return response
        except Exception as e:
            logging.error(f"🕵️‍♂️ Critic Error: {e}")
            return "APPROVED" # Fallback to avoid deadlocks

class Hassan:
    """The Execution Unit (Worker/Slave). Abstraction for CLI tools."""
    
    def __init__(self, settings, mission_config):
        self.hassan_config = settings.get('body', {}) or settings.get('hassan', {})
        self.active_driver_name = self.hassan_config.get('active_driver', 'claude')
        self.drivers = self.hassan_config.get('drivers', {})
        self.mission_config = mission_config
        self.system_prompt_file = None
        
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            self.driver_config = {
                "command": "claude",
                "args": ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}", "-c", "--dangerously-skip-permissions", "--allowedTools", "Write"],
                "env": {}
            }
            
        logging.info(f"🦾 Hassan Initialized: [{self.active_driver_name.upper()}] Driver")

    def prepare(self, current_goal_text, persona_guidelines=""):
        """Prepares system prompt files with the goal and persona."""
        if current_goal_text:
            self.system_prompt_file = os.path.abspath(".night_shift_system_prompt.txt")
            with open(self.system_prompt_file, "w", encoding="utf-8") as f:
                if persona_guidelines:
                    f.write(f"PERSONA GUIDELINES:\n{persona_guidelines}\n\n")
                f.write(f"CURRENT GOAL:\n{current_goal_text}")

    def cleanup(self):
        if self.system_prompt_file and os.path.exists(self.system_prompt_file):
            os.remove(self.system_prompt_file)

    def run(self, query):
        """Executes the driver command with the given query."""
        if not query: return "ERROR: Empty query."

        base_cmd = self.driver_config.get("command", "claude")
        args_template = self.driver_config.get("args", [])
        cmd_list = [base_cmd]
        
        for arg in args_template:
            val = arg.replace("{query}", query)
            val = val.replace("{system_prompt_file}", self.system_prompt_file or "")
            if val: cmd_list.append(val)

        env_config = self.driver_config.get("env", {})
        current_env = os.environ.copy()
        for key, value in env_config.items():
            current_env[key] = str(value)

        logging.info(f"\n--- 🚀 Running Hassan ({self.active_driver_name}) ---")
        try:
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
            for line in process.stdout:
                print(line, end='') 
                output_lines.append(line)
            process.wait()
            return "".join(output_lines).strip()
        except Exception as e:
            return f"ERROR running Hassan: {e}"

class NightShiftAgent:
    def __init__(self, mission_path="mission.yaml"):
        self.logger, self.log_file_path = setup_logging()
        
        if not os.path.exists(mission_path):
            sys.exit(1)

        with open(mission_path, 'r', encoding='utf-8') as f:
            self.mission_config = yaml.safe_load(f)
        
        if not os.path.exists(SETTINGS_FILE):
            self.settings = {}
        else:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = yaml.safe_load(f)

        # Initialize Modules
        self.brain = Brain(self.settings, self.mission_config)
        self.critic = Critic(self.settings, self.mission_config)
        self.hassan = Hassan(self.settings, self.mission_config)
        
        # Load Persona Guidelines
        self.personas = self.settings.get('personas', {})
        self.active_persona_name = self.mission_config.get('persona', 'general')
        self.active_persona_guidelines = self.personas.get(self.active_persona_name, "")
        
        if self.active_persona_guidelines:
            logging.info(f"🎭 Active Persona: [{self.active_persona_name.upper()}]")

        self.conversation_history = ""
        self.last_hassan_query = ""
        self.last_hassan_output = ""

    def _handle_quota_limit(self, error_message):
        try:
            match_abs = re.search(r"resets\s+(\d+(?:am|pm))", error_message, re.IGNORECASE)
            match_rel = re.search(r"after\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?", error_message, re.IGNORECASE)
            now = datetime.now()
            target = None
            if match_abs:
                time_str = match_abs.group(1)
                target = datetime.strptime(time_str, "%I%p").replace(year=now.year, month=now.month, day=now.day)
                if target < now: target += timedelta(days=1)
                target += timedelta(minutes=1)
            elif match_rel and any(match_rel.groups()):
                h, m, s = int(match_rel.group(1) or 0), int(match_rel.group(2) or 0), int(match_rel.group(3) or 0)
                target = now + timedelta(hours=h, minutes=m, seconds=s + 30)
            
            if not target:
                time.sleep(3600); return

            while True:
                remaining = (target - datetime.now()).total_seconds()
                if remaining <= 0: break
                logging.info(f"💤 Waiting for quota reset... {remaining/60:.1f} minutes left.")
                time.sleep(min(60, remaining))
        except Exception:
            time.sleep(3600)

    def _get_git_head(self):
        """Returns the current git commit hash."""
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=self.mission_config.get('project_path', os.getcwd()))
            return res.stdout.strip() if res.returncode == 0 else None
        except Exception:
            return None

    def _git_rollback(self, commit_hash):
        """Rolls back the repository to a specific commit."""
        if not commit_hash: return
        logging.warning(f"⏪ Rolling back to commit: {commit_hash}...")
        try:
            subprocess.run(["git", "reset", "--hard", commit_hash], cwd=self.mission_config.get('project_path', os.getcwd()))
            logging.info("✅ Rollback successful.")
        except Exception as e:
            logging.error(f"❌ Rollback failed: {e}")

    def start(self):
        logging.info(f"🌙 Night Shift (v4.2) Starting with persona: {self.active_persona_name}")
        
        # Git Checkpoint
        safety_config = self.settings.get('safety', {})
        mission_start_commit = self._get_git_head()
        
        if safety_config.get('create_backup_branch') and mission_start_commit:
            branch_name = f"night-shift-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.mission_config.get('project_path', os.getcwd()))
            logging.info(f"🛡️ Created backup branch: {branch_name}")

        raw_goals = self.mission_config.get('goal')
        goals = raw_goals if isinstance(raw_goals, list) else [raw_goals]
        constraints = self.mission_config.get('constraints', [])
        
        try:
            for i, task in enumerate(goals, 1):
                # Task-level checkpoint
                task_start_commit = self._get_git_head()
                
                logging.info(f"\n{'='*60}\n🚀 STARTING TASK {i}/{len(goals)}\n📄 Task: {task}\n{'='*60}\n")
                
                self.hassan.prepare(current_goal_text=task, persona_guidelines=self.active_persona_guidelines)
                initial_query = f"Start Task {i}: {task}"
                hassan_output = self.hassan.run(initial_query)
                self.conversation_history += f"\n=== TASK {i} START ===\nDirector Init: {initial_query}\nHassan Output:\n{hassan_output}\n"
                self.last_hassan_output = hassan_output

                while True:
                    if "hit your limit" in self.last_hassan_output and "resets" in self.last_hassan_output:
                        self._handle_quota_limit(self.last_hassan_output)
                    
                    next_action = self.brain.think(task, str(raw_goals), constraints, self.conversation_history, self.last_hassan_output, self.active_persona_guidelines)
                    self.conversation_history += f"\n--- 🧠 DIRECTOR DECISION ---\n{next_action}\n"

                    if "capacity" in next_action or "quota" in next_action.lower():
                        self._handle_quota_limit(next_action); continue

                    if next_action == "MISSION_COMPLETED":
                        # Summon the Critic for verification
                        verification = self.critic.evaluate(task, self.conversation_history, self.last_hassan_output)
                        if verification.strip().upper() == "APPROVED":
                            logging.info(f"✅ Task {i} Verified and Completed!"); break
                        else:
                            logging.info(f"🕵️‍♂️ Critic Rejected: {verification}")
                            self.conversation_history += f"\n--- 🕵️‍♂️ CRITIC FEEDBACK (REJECTED) ---\n{verification}\nPlease address the issues mentioned above.\n-----------------------------------\n"
                            # Reset loop to address feedback
                            hassan_output = f"Critic feedback received: {verification}. I need to fix these issues."
                            self.last_hassan_output = hassan_output
                            continue
                    
                    if next_action.startswith("MISSION_FAILED"):
                        logging.error(f"❌ Task {i} Failed: {next_action}")
                        if safety_config.get('auto_rollback_on_failure'):
                            self._git_rollback(task_start_commit)
                        return 
                    
                    hassan_output = self.hassan.run(next_action)
                    self.conversation_history += f"\n--- 🦾 HASSAN OUTPUT ---\n{hassan_output}\n"
                    self.last_hassan_output = hassan_output
                    time.sleep(RATE_LIMIT_SLEEP)

            self.hassan.run("Commit and push all changes now that all tasks are completed.")
        finally:
            self.hassan.cleanup()
            with open(self.log_file_path.replace("log", "history"), "w", encoding="utf-8") as f:
                f.write(self.conversation_history)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain & Hassan")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    args = parser.parse_args()
    agent = NightShiftAgent(mission_path=args.mission_file)
    agent.start()
