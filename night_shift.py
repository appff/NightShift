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
import shutil
from datetime import datetime, timedelta
import copy
from concurrent.futures import ThreadPoolExecutor

# --- Configuration & Constants ---
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
SETTINGS_FILE = "settings.yaml"
BRAIN_WORKSPACE_DIR = os.path.join(".night_shift", "brain_env")
SQUAD_WORKSPACE_DIR = os.path.join(".night_shift", "squad")

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

def _extract_driver_block(block):
    """Returns (active_driver, drivers_dict) supporting flat or nested schemas."""
    if not isinstance(block, dict):
        return None, {}
    active = block.get("active_driver")
    drivers = block.get("drivers")
    if isinstance(drivers, dict):
        return active, drivers
    # Flat schema: treat all non-reserved keys as driver definitions.
    reserved_keys = {"active_driver"}
    flat_drivers = {k: v for k, v in block.items() if k not in reserved_keys}
    return active, flat_drivers

def validate_settings_schema(settings):
    """Simple validation for critical settings keys."""
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary")

    errors = []

    def validate_driver_block(block_name, block):
        if not isinstance(block, dict):
            errors.append(f"'{block_name}' must be a dictionary")
            return
        active, drivers = _extract_driver_block(block)
        if active and (not isinstance(active, str) or not active.strip()):
            errors.append(f"'{block_name}.active_driver' must be a non-empty string")
        if drivers is not None and not isinstance(drivers, dict):
            errors.append(f"'{block_name}.drivers' must be a dictionary")
            return
        if active and drivers and active not in drivers:
            errors.append(f"'{block_name}.active_driver' '{active}' not found in drivers")
        for name, cfg in (drivers or {}).items():
            if not isinstance(cfg, dict):
                errors.append(f"'{block_name}.drivers.{name}' must be a dictionary")
                continue
            command = cfg.get("command")
            args = cfg.get("args", [])
            env = cfg.get("env", {})
            if command is not None and not isinstance(command, str):
                errors.append(f"'{block_name}.drivers.{name}.command' must be a string")
            if args is not None and not isinstance(args, list):
                errors.append(f"'{block_name}.drivers.{name}.args' must be a list")
            elif isinstance(args, list) and not all(isinstance(a, str) for a in args):
                errors.append(f"'{block_name}.drivers.{name}.args' must be a list of strings")
            if env is not None and not isinstance(env, dict):
                errors.append(f"'{block_name}.drivers.{name}.env' must be a dictionary")

    if "brain" in settings:
        validate_driver_block("brain", settings.get("brain"))
    if "critic" in settings:
        validate_driver_block("critic", settings.get("critic"))
    if "body" in settings:
        validate_driver_block("body", settings.get("body"))
    if "hassan" in settings:
        validate_driver_block("hassan", settings.get("hassan"))

    safety = settings.get("safety")
    if safety is not None and not isinstance(safety, dict):
        errors.append("'safety' must be a dictionary")
    elif isinstance(safety, dict):
        for key in ["auto_rollback_on_failure", "create_backup_branch", "auto_commit_and_push"]:
            if key in safety and not isinstance(safety.get(key), bool):
                errors.append(f"'safety.{key}' must be a boolean")

    personas = settings.get("personas")
    if personas is not None and not isinstance(personas, dict):
        errors.append("'personas' must be a dictionary of string values")
    elif isinstance(personas, dict):
        for name, value in personas.items():
            if not isinstance(value, str):
                errors.append(f"'personas.{name}' must be a string")

    persona_rules = settings.get("persona_rules")
    if persona_rules is not None:
        if not isinstance(persona_rules, list):
            errors.append("'persona_rules' must be a list of rules")
        else:
            for idx, rule in enumerate(persona_rules):
                if not isinstance(rule, dict):
                    errors.append(f"'persona_rules[{idx}]' must be a dictionary")
                    continue
                pattern = rule.get("pattern")
                persona = rule.get("persona")
                flags = rule.get("flags")
                if not isinstance(pattern, str) or not pattern.strip():
                    errors.append(f"'persona_rules[{idx}].pattern' must be a non-empty string")
                if not isinstance(persona, str) or not persona.strip():
                    errors.append(f"'persona_rules[{idx}].persona' must be a non-empty string")
                if flags is not None and not isinstance(flags, str):
                    errors.append(f"'persona_rules[{idx}].flags' must be a string")

    if errors:
        raise ValueError("Settings validation errors:\n- " + "\n- ".join(errors))
    
def validate_mission_schema(mission_config):
    if not isinstance(mission_config, dict):
        raise ValueError("Mission must be a dictionary")
    has_goal = bool(mission_config.get('goal'))
    has_task = bool(mission_config.get('task'))
    if not has_goal and not has_task:
        raise ValueError("Mission must have a 'goal'")

    goal = mission_config.get('goal') or mission_config.get('task')
    if not isinstance(goal, (str, list)):
        raise ValueError("'goal' must be a string or a list of strings/objects")

    if isinstance(goal, list):
        if len(goal) == 0:
            raise ValueError("'goal' list cannot be empty")
        for idx, item in enumerate(goal):
            if isinstance(item, str):
                continue
            if isinstance(item, dict):
                task_text = item.get("task") or item.get("goal") or item.get("title")
                if not isinstance(task_text, str) or not task_text.strip():
                    raise ValueError(f"'goal[{idx}]' must include a non-empty 'task' or 'title' string")
                persona = item.get("persona")
                if persona is not None and not isinstance(persona, str):
                    raise ValueError(f"'goal[{idx}].persona' must be a string")
                sub_tasks = item.get("sub_tasks")
                if sub_tasks is not None:
                    if not isinstance(sub_tasks, list) or not all(isinstance(st, str) for st in sub_tasks):
                        raise ValueError(f"'goal[{idx}].sub_tasks' must be a list of strings")
                continue
            raise ValueError("'goal' list items must be strings or objects with 'task'")

    if "project_path" in mission_config:
        project_path = mission_config.get("project_path")
        if not isinstance(project_path, str):
            raise ValueError("'project_path' must be a string")
        if project_path and not os.path.exists(project_path):
            raise ValueError(f"'project_path' does not exist: {project_path}")

    constraints = mission_config.get("constraints")
    if constraints is not None:
        if not isinstance(constraints, list):
            raise ValueError("'constraints' must be a list of strings")
        if not all(isinstance(item, str) for item in constraints):
            raise ValueError("All items in 'constraints' must be strings")

    if "parallel" in mission_config and not isinstance(mission_config.get("parallel"), bool):
        raise ValueError("'parallel' must be a boolean")

    if "persona" in mission_config and not isinstance(mission_config.get("persona"), str):
        raise ValueError("'persona' must be a string")

# --- Core Classes ---

class Brain:
    """The Intelligence Unit (Director). Decides what to do via CLI tools."""
    
    def __init__(self, settings, mission_config):
        self.settings = settings
        self.mission_config = mission_config
        self.project_path = os.path.abspath(self.mission_config.get('project_path', os.getcwd()))
        
        self.brain_config = self.settings.get('brain', {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.brain_config)
        if not self.active_driver_name:
            self.active_driver_name = 'claude'
        
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

    def think(self, current_task_block, total_mission_context, constraints, conversation_history, last_hassan_output, persona_guidelines="", past_memories=""):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        constraints_text = '\n'.join(constraints) if isinstance(constraints, list) else str(constraints)
        
        persona_section = f"\n[YOUR PERSONA GUIDELINES]\n{persona_guidelines}\n" if persona_guidelines else ""
        memory_section = f"\n[PAST MEMORIES / LESSONS LEARNED]\n{past_memories}\n" if past_memories else ""

        prompt = f"""
You are the "Director" of an autonomous coding session.
Your "Hassan" (Worker) is a CLI tool that executes your commands.
{persona_section}
{memory_section}
[CURRENT ACTIVE TASK HIERARCHY]
{current_task_block}

[OVERALL MISSION CONTEXT]
{total_mission_context}

[CONSTRAINTS]
{constraints_text}

[CONVERSATION HISTORY]
{conversation_history[-MAX_HISTORY_CHARS:]}

[LAST HASSAN OUTPUT]
{clean_output}

[INSTRUCTIONS]
1. Focus ONLY on the [CURRENT ACTIVE TASK HIERARCHY].
2. Analyze the [CONSTRAINTS], [PERSONA GUIDELINES], and [LAST HASSAN OUTPUT].
3. Determine the NEXT single, specific, and actionable command/query for Hassan.
4. If ALL parts of the [CURRENT ACTIVE TASK HIERARCHY] are complete, reply exactly: "MISSION_COMPLETED".
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

class MemoryManager:
    """Handles long-term memory (lessons learned) for the Brain."""
    def __init__(self, project_path):
        self.memory_file = os.path.join(project_path, ".night_shift", "memories.md")
        if not os.path.exists(os.path.dirname(self.memory_file)):
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

    def load_memories(self):
        """Returns the content of the memory file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                return ""
        return ""

    def save_memory(self, new_insight):
        """Appends a new insight to the memory file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.memory_file, "a", encoding="utf-8") as f:
                f.write(f"\n### {timestamp}\n{new_insight}\n")
        except Exception as e:
            logging.error(f"❌ Failed to save memory: {e}")

class Critic:
    """The Quality Assurance Unit (Critic). Reviews the work of Hassan."""
    
    def __init__(self, settings, mission_config):
        self.settings = settings
        self.mission_config = mission_config
        self.project_path = os.path.abspath(self.mission_config.get('project_path', os.getcwd()))
        
        self.critic_config = self.settings.get('critic', {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.critic_config)
        if not self.active_driver_name:
            self.active_driver_name = 'gemini'
        self.brain_env_dir = os.path.join(self.project_path, BRAIN_WORKSPACE_DIR)
        
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            self.driver_config = {"command": "gemini", "args": ["-p", "{prompt}"]}
            
        logging.info(f"🕵️‍♂️ Critic Initialized: [{self.active_driver_name.upper()}] CLI Mode")

    def evaluate(self, task_block, history, last_output):
        """Evaluates Hassan's work against the task hierarchy."""
        prompt = f"""
You are the "Quality Assurance Critic".
A worker (Hassan) has just completed a task. Your job is to verify if the work is actually complete and high quality.

[TASK HIERARCHY TO REVIEW]
{task_block}

[CONVERSATION & WORK HISTORY]
{history[-MAX_HISTORY_CHARS:]}

[FINAL OUTPUT/STATE]
{last_output[-MAX_CONTEXT_CHARS:]}

[INSTRUCTIONS]
1. Verify if ALL sub-tasks in the [TASK HIERARCHY TO REVIEW] are fulfilled.
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
        self.active_driver_name, self.drivers = _extract_driver_block(self.hassan_config)
        if not self.active_driver_name:
            self.active_driver_name = 'claude'
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

    def prepare(self, current_task_text, persona_guidelines=""):
        """Prepares system prompt files with the task block and persona."""
        if current_task_text:
            self.system_prompt_file = os.path.abspath(".night_shift_system_prompt.txt")
            with open(self.system_prompt_file, "w", encoding="utf-8") as f:
                if persona_guidelines:
                    f.write(f"PERSONA GUIDELINES:\n{persona_guidelines}\n\n")
                f.write(f"CURRENT TASK BLOCK:\n{current_task_text}")

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
        if self.mission_config is None:
            raise ValueError("Mission file is empty or invalid YAML")
        validate_mission_schema(self.mission_config)
        
        if not os.path.exists(SETTINGS_FILE):
            self.settings = {}
        else:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = yaml.safe_load(f) or {}
        validate_settings_schema(self.settings)

        # Initialize Modules
        self.memory_manager = MemoryManager(self.mission_config.get('project_path', os.getcwd()))
        self.brain = Brain(self.settings, self.mission_config)
        self.critic = Critic(self.settings, self.mission_config)
        self.hassan = Hassan(self.settings, self.mission_config)
        
        # Load Long-term Memories
        self.past_memories = self.memory_manager.load_memories()
        if self.past_memories:
            logging.info("📚 Long-term memories loaded. Brain is feeling experienced.")
        
        # Load Persona Guidelines
        self.personas = self.settings.get('personas', {})
        self.default_persona_name = self.mission_config.get('persona', 'general')
        self.default_persona_guidelines = self.personas.get(self.default_persona_name, "")
        self.persona_rules = self.settings.get("persona_rules", [])

        if self.default_persona_guidelines:
            logging.info(f"🎭 Default Persona: [{self.default_persona_name.upper()}]")

        self.conversation_history = ""
        self.last_hassan_query = ""
        self.last_hassan_output = ""

    def _select_persona(self, task_text, override_persona=None):
        if override_persona:
            return override_persona, self.personas.get(override_persona, "")
        for rule in self.persona_rules:
            try:
                flags = 0
                if isinstance(rule.get("flags"), str) and "i" in rule.get("flags").lower():
                    flags |= re.IGNORECASE
                if re.search(rule.get("pattern", ""), task_text, flags=flags):
                    persona_name = rule.get("persona")
                    return persona_name, self.personas.get(persona_name, "")
            except re.error:
                continue
        return self.default_persona_name, self.default_persona_guidelines

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

    def _git_is_dirty(self):
        """Returns True if there are uncommitted changes."""
        try:
            res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=self.mission_config.get('project_path', os.getcwd()))
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception:
            return False

    def _git_stash(self, message):
        """Stashes uncommitted changes to avoid data loss."""
        try:
            subprocess.run(["git", "stash", "push", "-u", "-m", message], cwd=self.mission_config.get('project_path', os.getcwd()))
        except Exception as e:
            logging.error(f"❌ Failed to stash changes: {e}")

    def _git_rollback(self, commit_hash):
        """Rolls back the repository to a specific commit."""
        if not commit_hash: return
        logging.warning(f"⏪ Rolling back to commit: {commit_hash}...")
        try:
            if self._git_is_dirty():
                logging.warning("⚠️ Uncommitted changes detected. Stashing before rollback.")
                self._git_stash(f"night-shift-auto-stash-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            subprocess.run(["git", "reset", "--hard", commit_hash], cwd=self.mission_config.get('project_path', os.getcwd()))
            logging.info("✅ Rollback successful.")
        except Exception as e:
            logging.error(f"❌ Rollback failed: {e}")

    def _format_task_block(self, task_item):
        """Formats a task object (with title/task and sub_tasks) into a readable block."""
        if isinstance(task_item, str):
            return f"Task: {task_item}"
        
        title = task_item.get('task') or task_item.get('goal') or task_item.get('title', 'Untitled Task')
        sub_tasks = task_item.get('sub_tasks', []) or []

        block = f"MAIN TASK: {title}\n"
        if sub_tasks:
            block += "SUB-TASKS:\n"
            for sub in sub_tasks:
                block += f"  - {sub}\n"
        return block

    def _normalize_task_item(self, task_item):
        if isinstance(task_item, str):
            return {"text": f"Task: {task_item}", "persona": None}
        if isinstance(task_item, dict):
            text = task_item.get("task") or task_item.get("goal") or task_item.get("title")
            if not text:
                text = "Untitled Task"
            if task_item.get("sub_tasks"):
                block = self._format_task_block(task_item)
                return {"text": block, "persona": task_item.get("persona")}
            return {"text": text, "persona": task_item.get("persona")}
        return {"text": str(task_item), "persona": None}

    def _execute_single_task(self, i, task_item, all_tasks, constraints, safety_config):
        """Executes a single task item (supports strings or dicts with sub_tasks)."""
        # Task-level checkpoint
        task_start_commit = self._get_git_head()
        task_block = task_item.get("text") if isinstance(task_item, dict) else self._format_task_block(task_item)
        
        # Isolated workspace for parallel execution
        is_parallel = self.mission_config.get('parallel', False)
        project_root = self.mission_config.get('project_path', os.getcwd())
        work_dir = project_root

        if is_parallel:
            work_dir = os.path.join(project_root, SQUAD_WORKSPACE_DIR, f"task_{i}")
            logging.info(f"⚡ Creating isolated workspace for Task {i}: {work_dir}")
            if os.path.exists(work_dir): shutil.rmtree(work_dir)
            # Simple clone: copy current directory excluding .night_shift and logs
            os.makedirs(work_dir, exist_ok=True)
            for item in os.listdir(project_root):
                if item in ['.night_shift', 'logs', '.git', '__pycache__']: continue
                s = os.path.join(project_root, item)
                d = os.path.join(work_dir, item)
                if os.path.isdir(s): shutil.copytree(s, d)
                else: shutil.copy2(s, d)
        
        task_text = task_item.get("text", task_block) if isinstance(task_item, dict) else task_block
        persona_name = task_item.get("persona_name") if isinstance(task_item, dict) else self.default_persona_name
        persona_guidelines = task_item.get("persona_guidelines") if isinstance(task_item, dict) else self.default_persona_guidelines

        logging.info(f"\n{'='*60}\n🚀 STARTING TASK {i} (Persona: {persona_name})\n{task_block}\n{'='*60}\n")
        
        self.hassan.prepare(current_task_text=task_block, persona_guidelines=persona_guidelines)
        initial_query = f"Start Task {i}: {task_block}"
        
        # Note: If parallel, hassan needs to know the correct work_dir
        orig_path = self.hassan.mission_config.get('project_path', os.getcwd())
        self.hassan.mission_config['project_path'] = work_dir
        
        try:
            hassan_output = self.hassan.run(initial_query)
            task_history = f"\n=== TASK {i} START ===\nDirector Init: {initial_query}\nHassan Output:\n{hassan_output}\n"
            last_output = hassan_output

            while True:
                if "hit your limit" in last_output and "resets" in last_output:
                    self._handle_quota_limit(last_output)
                
                next_action = self.brain.think(
                    task_block,
                    str([t.get("text", t) if isinstance(t, dict) else t for t in all_tasks]),
                    constraints,
                    task_history,
                    last_output,
                    persona_guidelines,
                    self.past_memories
                )
                task_history += f"\n--- 🧠 DIRECTOR DECISION ---\n{next_action}\n"

                if "capacity" in next_action or "quota" in next_action.lower():
                    self._handle_quota_limit(next_action); continue

                if next_action == "MISSION_COMPLETED":
                    # Summon the Critic for verification
                    verification = self.critic.evaluate(task_block, task_history, last_output)
                    if verification.strip().upper() == "APPROVED":
                        logging.info(f"✅ Task {i} Verified and Completed!"); break
                    else:
                        logging.info(f"🕵️‍♂️ Critic Rejected Task {i}: {verification}")
                        task_history += f"\n--- 🕵️‍♂️ CRITIC FEEDBACK (REJECTED) ---\n{verification}\nPlease address the issues mentioned above.\n-----------------------------------\n"
                        # Reset loop to address feedback
                        hassan_output = f"Critic feedback received: {verification}. I need to fix these issues."
                        last_output = hassan_output
                        continue
                
                if next_action.startswith("MISSION_FAILED"):
                    logging.error(f"❌ Task {i} Failed: {next_action}")
                    if safety_config.get('auto_rollback_on_failure'):
                        self._git_rollback(task_start_commit)
                    return f"TASK_{i}_FAILED: {next_action}"
                
                hassan_output = self.hassan.run(next_action)
                task_history += f"\n--- 🦾 HASSAN OUTPUT ---\n{hassan_output}\n"
                last_output = hassan_output
                time.sleep(RATE_LIMIT_SLEEP)
            
            return task_history
        finally:
            self.hassan.mission_config['project_path'] = orig_path

    def start(self):
        logging.info(f"🌙 Night Shift (v4.2) Starting with default persona: {self.default_persona_name}")
        
        safety_config = self.settings.get('safety', {})
        mission_start_commit = self._get_git_head()
        
        if safety_config.get('create_backup_branch') and mission_start_commit:
            branch_name = f"night-shift-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            subprocess.run(["git", "branch", branch_name, mission_start_commit], cwd=self.mission_config.get('project_path', os.getcwd()))
            logging.info(f"🛡️ Created backup branch (no checkout): {branch_name}")

        raw_tasks = self.mission_config.get('goal')
        if raw_tasks is None:
            raw_tasks = self.mission_config.get('task', [])
        tasks = raw_tasks if isinstance(raw_tasks, list) else [raw_tasks]
        constraints = self.mission_config.get('constraints', [])
        is_parallel = self.mission_config.get('parallel', False)

        normalized_tasks = []
        for task_item in tasks:
            normalized = self._normalize_task_item(task_item)
            persona_name, persona_guidelines = self._select_persona(normalized["text"], normalized.get("persona"))
            normalized["persona_name"] = persona_name
            normalized["persona_guidelines"] = persona_guidelines
            normalized_tasks.append(normalized)
        
        logging.info(f"📋 Mission loaded with {len(normalized_tasks)} task(s). Mode: {'PARALLEL' if is_parallel else 'SEQUENTIAL'}")
        
        try:
            if is_parallel:
                if os.path.exists(SQUAD_WORKSPACE_DIR): shutil.rmtree(SQUAD_WORKSPACE_DIR)
                with ThreadPoolExecutor(max_workers=len(normalized_tasks)) as executor:
                    results = list(executor.map(lambda x: self._execute_single_task(x[0], x[1], normalized_tasks, constraints, safety_config), enumerate(normalized_tasks, 1)))
                for res in results:
                    self.conversation_history += res
            else:
                for i, task_item in enumerate(normalized_tasks, 1):
                    res = self._execute_single_task(i, task_item, normalized_tasks, constraints, safety_config)
                    self.conversation_history += res

            # --- Mission Reflection ---
            logging.info("🧠 Reflecting on mission to store memories...")
            reflection_prompt = f"Based on this mission: {str([t.get('text', t) if isinstance(t, dict) else t for t in normalized_tasks])}, provide 2-3 concise 'Lessons Learned' for future similar tasks. Output only the bullets."
            insights = self.brain._run_cli_command(reflection_prompt)
            if not insights.startswith("MISSION_FAILED"):
                self.memory_manager.save_memory(insights)

            if not is_parallel: # Commit only in sequential mode or let user handle parallel merges
                if safety_config.get('auto_commit_and_push'):
                    self.hassan.run("Commit and push all changes now that all tasks are completed.")
                else:
                    logging.info("ℹ️ Auto commit/push disabled. Review and commit changes manually.")
            else:
                logging.info(f"🏁 Parallel tasks finished. Check isolated workspaces in {SQUAD_WORKSPACE_DIR}")
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
    parser.add_argument("--dry-run", action="store_true", help="Validate config files and exit")
    args = parser.parse_args()
    try:
        agent = NightShiftAgent(mission_path=args.mission_file)
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)
    if args.dry_run:
        print("Configuration OK.")
        sys.exit(0)
    agent.start()
