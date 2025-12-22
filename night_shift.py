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

import os
import sys

# Auto-reexec with venv if PyYAML isn't available in system Python.
try:
    import yaml  # noqa: F401
except Exception:
    venv_python = os.path.join(os.getcwd(), ".venv", "bin", "python3")
    if os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)
    raise

import subprocess
import time
import re
import argparse
import logging
import shutil
import json
import fnmatch
import yaml
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
IGNORE_FILE = ".night_shiftignore"

# LLM Limits
MAX_CONTEXT_CHARS = 3000
MAX_HISTORY_CHARS = 4000
MAX_TOKENS = 1024
RATE_LIMIT_SLEEP = 2

# --- Utils ---
def setup_logging(log_dir=LOG_DIR, log_level=logging.INFO):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file_path = os.path.join(log_dir, f"night_shift_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
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
    reserved_keys = {"active_driver", "active_drivers", "voting", "timeout", "retries", "retry_backoff", "output_format", "home_dir", "link_auth", "strictness"}
    flat_drivers = {k: v for k, v in block.items() if k not in reserved_keys}
    return active, flat_drivers

def _redact_cmd(cmd_list):
    sensitive_flags = {"--api-key", "--token", "--password", "--key"}
    redacted = []
    redact_next = False
    for arg in cmd_list:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        if arg in sensitive_flags:
            redacted.append(arg)
            redact_next = True
            continue
        if re.search(r"(api_key|token|password|secret)=", arg, re.IGNORECASE):
            key, _sep, _val = arg.partition("=")
            redacted.append(f"{key}=<redacted>")
            continue
        redacted.append(arg)
    return redacted

def _load_ignore_patterns(root_path):
    ignore_path = os.path.join(root_path, IGNORE_FILE)
    if not os.path.exists(ignore_path):
        return []
    patterns = []
    try:
        with open(ignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
    except Exception:
        return []
    return patterns

def _link_auth_folders(target_home):
    real_home = os.path.expanduser("~")
    auth_folders = [".claude", ".gemini", ".codex", ".config"]
    auth_files = [".claude.json", ".gemini.json", ".codex.json"]
    for folder in auth_folders:
        src = os.path.join(real_home, folder)
        dst = os.path.join(target_home, folder)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.symlink(src, dst)
            except Exception:
                pass
    for fname in auth_files:
        src = os.path.join(real_home, fname)
        dst = os.path.join(target_home, fname)
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

def _is_ignored(path, root_path, patterns):
    rel_path = os.path.relpath(path, root_path)
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
            return True
    return False

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
        output_format = settings.get("brain", {}).get("output_format")
        if output_format is not None and output_format not in ("text", "json"):
            errors.append("'brain.output_format' must be 'text' or 'json'")
        home_dir = settings.get("brain", {}).get("home_dir")
        if home_dir is not None and not isinstance(home_dir, str):
            errors.append("'brain.home_dir' must be a string")
        link_auth = settings.get("brain", {}).get("link_auth")
        if link_auth is not None and not isinstance(link_auth, bool):
            errors.append("'brain.link_auth' must be a boolean")
    if "critic" in settings:
        validate_driver_block("critic", settings.get("critic"))
        critic = settings.get("critic", {})
        active_drivers = critic.get("active_drivers")
        if active_drivers is not None:
            if not isinstance(active_drivers, list) or not all(isinstance(d, str) for d in active_drivers):
                errors.append("'critic.active_drivers' must be a list of strings")
        voting = critic.get("voting")
        if voting is not None and voting not in ("all", "majority"):
            errors.append("'critic.voting' must be 'all' or 'majority'")
        home_dir = critic.get("home_dir")
        if home_dir is not None and not isinstance(home_dir, str):
            errors.append("'critic.home_dir' must be a string")
        link_auth = critic.get("link_auth")
        if link_auth is not None and not isinstance(link_auth, bool):
            errors.append("'critic.link_auth' must be a boolean")
    if "body" in settings:
        validate_driver_block("body", settings.get("body"))
        home_dir = settings.get("body", {}).get("home_dir")
        if home_dir is not None and not isinstance(home_dir, str):
            errors.append("'body.home_dir' must be a string")
        link_auth = settings.get("body", {}).get("link_auth")
        if link_auth is not None and not isinstance(link_auth, bool):
            errors.append("'body.link_auth' must be a boolean")
    if "hassan" in settings:
        validate_driver_block("hassan", settings.get("hassan"))

    safety = settings.get("safety")
    if safety is not None and not isinstance(safety, dict):
        errors.append("'safety' must be a dictionary")
    elif isinstance(safety, dict):
        for key in ["auto_rollback_on_failure", "create_backup_branch", "auto_commit_and_push", "require_approval_for_destructive", "preview_changes", "use_worktrees"]:
            if key in safety and not isinstance(safety.get(key), bool):
                errors.append(f"'safety.{key}' must be a boolean")

    personas = settings.get("personas")
    if personas is not None and not isinstance(personas, dict):
        errors.append("'personas' must be a dictionary of string values")
    elif isinstance(personas, dict):
        for name, value in personas.items():
            if not isinstance(value, str):
                errors.append(f"'personas.{name}' must be a string")

    tools = settings.get("tools")
    if tools is not None and not isinstance(tools, list):
        errors.append("'tools' must be a list of strings")
    elif isinstance(tools, list) and not all(isinstance(t, str) for t in tools):
        errors.append("'tools' must be a list of strings")

    planner = settings.get("planner")
    if planner is not None and not isinstance(planner, dict):
        errors.append("'planner' must be a dictionary")
    elif isinstance(planner, dict):
        if "enabled" in planner and not isinstance(planner.get("enabled"), bool):
            errors.append("'planner.enabled' must be a boolean")
        if "require_approval" in planner and not isinstance(planner.get("require_approval"), bool):
            errors.append("'planner.require_approval' must be a boolean")

    qa = settings.get("qa")
    if qa is not None and not isinstance(qa, dict):
        errors.append("'qa' must be a dictionary")
    elif isinstance(qa, dict):
        if "run_tests" in qa and not isinstance(qa.get("run_tests"), bool):
            errors.append("'qa.run_tests' must be a boolean")
        if "test_on_each_task" in qa and not isinstance(qa.get("test_on_each_task"), bool):
            errors.append("'qa.test_on_each_task' must be a boolean")
        if "test_command" in qa and not isinstance(qa.get("test_command"), str):
            errors.append("'qa.test_command' must be a string")

    memory = settings.get("memory")
    if memory is not None and not isinstance(memory, dict):
        errors.append("'memory' must be a dictionary")
    elif isinstance(memory, dict):
        if "scope" in memory and memory.get("scope") not in ("project", "global", "both"):
            errors.append("'memory.scope' must be one of: project, global, both")

    parallel = settings.get("parallel")
    if parallel is not None and not isinstance(parallel, dict):
        errors.append("'parallel' must be a dictionary")
    elif isinstance(parallel, dict):
        if "max_workers" in parallel and not isinstance(parallel.get("max_workers"), int):
            errors.append("'parallel.max_workers' must be an integer")

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

    if "reviewer_mode" in mission_config and not isinstance(mission_config.get("reviewer_mode"), bool):
        raise ValueError("'reviewer_mode' must be a boolean")

# --- Core Classes ---

class Brain:
    """The Intelligence Unit (Director). Decides what to do via CLI tools."""
    
    def __init__(self, settings, mission_config, log_dir=LOG_DIR):
        self.settings = settings
        self.mission_config = mission_config
        self.project_path = os.path.abspath(self.mission_config.get('project_path', os.getcwd()))
        self.log_dir = log_dir
        
        self.brain_config = self.settings.get('brain', {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.brain_config)
        if not self.active_driver_name:
            self.active_driver_name = 'claude'
        self.link_auth = self.brain_config.get("link_auth", True)
        
        # Setup Brain Workspace (Metadata Isolation)
        configured_home = self.brain_config.get("home_dir")
        if configured_home:
            self.brain_env_dir = os.path.abspath(os.path.expanduser(configured_home))
        else:
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
        self._select_available_driver()
        self.timeout = int(self.driver_config.get("timeout", 300))
        self.retries = int(self.driver_config.get("retries", 0))
        self.retry_backoff = float(self.driver_config.get("retry_backoff", 1.5))
            
        logging.info(f"🧠 Brain Initialized: [{self.active_driver_name.upper()}] CLI Mode")

    def _select_available_driver(self):
        command = self.driver_config.get("command")
        if command and shutil.which(command):
            return
        for name, cfg in self.drivers.items():
            cmd = cfg.get("command")
            if cmd and shutil.which(cmd):
                logging.warning(f"⚠️ Brain Driver '{self.active_driver_name}' unavailable. Falling back to '{name}'.")
                self.active_driver_name = name
                self.driver_config = cfg
                return
        logging.error(f"❌ No available Brain driver found (last command: {command}).")

    def _setup_auth_links(self):
        """Symlinks common AI CLI auth folders from real HOME to Brain's isolated HOME."""
        if not self.link_auth:
            return
        _link_auth_folders(self.brain_env_dir)

    def clean_ansi(self, text):
        return ANSI_ESCAPE_PATTERN.sub('', text)

    def _log_brain_activity(self, message):
        """Logs detailed brain activity to a separate debug log file."""
        brain_log_file = os.path.join(self.log_dir, f"brain_log_{datetime.now().strftime('%Y%m%d')}.txt")
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
        logging.debug(f"🧠 Brain Command: {' '.join(_redact_cmd(cmd_list))}")
        
        brain_env = os.environ.copy()
        brain_env["HOME"] = self.brain_env_dir
        
        attempt = 0
        while True:
            try:
                process = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    env=brain_env,
                    check=False,
                    timeout=self.timeout
                )

                if process.returncode != 0:
                    error_msg = process.stderr.strip()
                    logging.error(f"🧠 Brain CLI Error ({process.returncode}): {error_msg}")
                    if attempt < self.retries:
                        attempt += 1
                        time.sleep(self.retry_backoff ** attempt)
                        continue
                    return f"MISSION_FAILED: Brain CLI Error - {error_msg}"

                return process.stdout.strip()

            except subprocess.TimeoutExpired:
                logging.error(f"🧠 Brain CLI Timeout ({self.timeout}s expired).")
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff ** attempt)
                    continue
                return "MISSION_FAILED: Brain CLI Timeout"
            except Exception as e:
                logging.error(f"🧠 Brain Execution Exception: {e}")
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff ** attempt)
                    continue
                return f"MISSION_FAILED: {e}"

    def think(self, current_task_block, total_mission_context, constraints, conversation_history, last_hassan_output, persona_guidelines="", past_memories="", tool_registry="", output_format="text"):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        constraints_text = '\n'.join(constraints) if isinstance(constraints, list) else str(constraints)
        tools_section = f"\n[TOOL REGISTRY]\n{tool_registry}\n" if tool_registry else ""
        format_section = ""
        if output_format == "json":
            format_section = """
[OUTPUT FORMAT]
Return ONLY valid JSON with:
{"command": "<next action command>", "status": "continue"} OR {"command": "", "status": "completed"}.
Do not include markdown or extra text.
"""
        
        persona_section = f"\n[YOUR PERSONA GUIDELINES]\n{persona_guidelines}\n" if persona_guidelines else ""
        memory_section = f"\n[PAST MEMORIES / LESSONS LEARNED]\n{past_memories}\n" if past_memories else ""

        output_instruction = "5. Output ONLY the command string."
        if output_format == "json":
            output_instruction = "5. Output ONLY valid JSON as specified in [OUTPUT FORMAT]."

        prompt = f"""
You are the "Director" of an autonomous coding session.
Your "Hassan" (Worker) is a CLI tool that executes your commands.
{persona_section}
{memory_section}
{tools_section}
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
{output_instruction}

[CRITICAL RULE]
- Keep commands CONCISE.
- Do NOT repeat the exact same command if it failed.
"""
        if format_section:
            prompt += format_section
        log_entry = f"\n{'='*80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'='*80}\n{prompt}\n"
        self._log_brain_activity(log_entry)

        response_text = self._run_cli_command(prompt)
        logging.info(f"--- 🧠 BRAIN RESPONSE ---\n{response_text}\n--- END RESPONSE ---")
        self._log_brain_activity(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-'*80}\n{response_text}\n")
        return response_text

class MemoryManager:
    """Handles long-term memory (lessons learned) for the Brain."""
    def __init__(self, project_path, scope="project"):
        self.scope = scope
        self.project_memory_file = os.path.join(project_path, ".night_shift", "memories.md")
        self.global_memory_file = os.path.expanduser("~/.night_shift/memories.md")
        try:
            if not os.path.exists(os.path.dirname(self.project_memory_file)):
                os.makedirs(os.path.dirname(self.project_memory_file), exist_ok=True)
        except Exception:
            pass
        try:
            if not os.path.exists(os.path.dirname(self.global_memory_file)):
                os.makedirs(os.path.dirname(self.global_memory_file), exist_ok=True)
        except Exception:
            pass

    def load_memories(self):
        """Returns the content of the memory file."""
        memories = []
        files = []
        if self.scope in ("project", "both"):
            files.append(self.project_memory_file)
        if self.scope in ("global", "both"):
            files.append(self.global_memory_file)
        for path in files:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            memories.append(content)
                except Exception:
                    continue
        return "\n\n".join(memories).strip()

    def save_memory(self, new_insight):
        """Appends a new insight to the memory file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        targets = []
        if self.scope in ("project", "both"):
            targets.append(self.project_memory_file)
        if self.scope in ("global", "both"):
            targets.append(self.global_memory_file)
        for path in targets:
            try:
                with open(path, "a", encoding="utf-8") as f:
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
        self.active_driver_names = self.critic_config.get('active_drivers', [])
        if isinstance(self.active_driver_names, str):
            self.active_driver_names = [self.active_driver_names]
        if not self.active_driver_names:
            self.active_driver_names = [self.active_driver_name]
        self.active_driver_names = self._filter_available_drivers(self.active_driver_names)
        self.voting_mode = self.critic_config.get("voting", "all")
        configured_home = self.critic_config.get("home_dir")
        if configured_home:
            self.brain_env_dir = os.path.abspath(os.path.expanduser(configured_home))
        else:
            self.brain_env_dir = os.path.join(self.project_path, BRAIN_WORKSPACE_DIR)
        self.link_auth = self.critic_config.get("link_auth", True)
        if self.brain_env_dir:
            os.makedirs(self.brain_env_dir, exist_ok=True)
            if self.link_auth:
                _link_auth_folders(self.brain_env_dir)
        self.timeout = int(self.critic_config.get("timeout", 300))
        self.retries = int(self.critic_config.get("retries", 0))
        self.retry_backoff = float(self.critic_config.get("retry_backoff", 1.5))

        logging.info(f"🕵️‍♂️ Critic Initialized: {', '.join([n.upper() for n in self.active_driver_names])} CLI Mode")

    def _filter_available_drivers(self, names):
        available = []
        for name in names:
            cfg = self.drivers.get(name, {})
            cmd = cfg.get("command")
            if cmd and shutil.which(cmd):
                available.append(name)
        if not available:
            for name, cfg in self.drivers.items():
                cmd = cfg.get("command")
                if cmd and shutil.which(cmd):
                    available.append(name)
        if not available:
            logging.error("❌ No available Critic drivers found.")
            return []
        return available

    def _run_with_driver(self, driver_name, prompt):
        driver_config = self.drivers.get(driver_name)
        if not driver_config:
            driver_config = {"command": "gemini", "args": ["-p", "{prompt}"]}

        brain_env = os.environ.copy()
        brain_env["HOME"] = self.brain_env_dir

        attempt = 0
        while True:
            try:
                cmd_list = [driver_config['command']]
                for arg in driver_config.get('args', []):
                    val = arg.replace("{prompt}", prompt)
                    if val:
                        cmd_list.append(val)

                logging.info(f"🕵️‍♂️ Critic is reviewing work via {driver_config['command']}...")
                logging.debug(f"🕵️‍♂️ Critic Command: {' '.join(_redact_cmd(cmd_list))}")
                process = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    text=True,
                    cwd=self.project_path,
                    env=brain_env,
                    timeout=self.timeout
                )
                response = process.stdout.strip()
                if process.returncode != 0 and attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff ** attempt)
                    continue
                return response
            except Exception as e:
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff ** attempt)
                    continue
                logging.error(f"🕵️‍♂️ Critic Error: {e}")
                return "APPROVED"

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
1. Verify if all key parts of the [TASK HIERARCHY TO REVIEW] are fulfilled.
2. Focus on major issues (functional failures, missing core requirements).
3. Ignore minor style nits or optional improvements.
4. If everything is acceptable, reply exactly: "APPROVED".
5. If there are blocking issues, provide a CONCISE list of fixes.
6. Output ONLY "APPROVED" or your feedback.
"""
        responses = []
        approvals = 0
        for driver_name in self.active_driver_names:
            response = self._run_with_driver(driver_name, prompt)
            responses.append((driver_name, response))
            if response.strip().upper() == "APPROVED":
                approvals += 1

        if self.voting_mode == "majority":
            if approvals >= (len(self.active_driver_names) // 2 + 1):
                return "APPROVED"
        else:
            if approvals == len(self.active_driver_names):
                return "APPROVED"

        feedback_lines = []
        for driver_name, response in responses:
            if response.strip().upper() != "APPROVED":
                feedback_lines.append(f"[{driver_name}] {response}")
        return "\n".join(feedback_lines) if feedback_lines else "APPROVED"

class Hassan:
    """The Execution Unit (Worker/Slave). Abstraction for CLI tools."""
    
    def __init__(self, settings, mission_config):
        self.hassan_config = settings.get('body', {}) or settings.get('hassan', {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.hassan_config)
        if not self.active_driver_name:
            self.active_driver_name = 'claude'
        self.mission_config = mission_config
        self.system_prompt_file = None
        self.home_dir = None
        configured_home = self.hassan_config.get("home_dir")
        if configured_home:
            self.home_dir = os.path.abspath(os.path.expanduser(configured_home))
        self.link_auth = self.hassan_config.get("link_auth", True)
        if self.home_dir:
            os.makedirs(self.home_dir, exist_ok=True)
            if self.link_auth:
                _link_auth_folders(self.home_dir)
        
        self.driver_config = self.drivers.get(self.active_driver_name)
        if not self.driver_config:
            self.driver_config = {
                "command": "claude",
                "args": ["--system-prompt-file", "{system_prompt_file}", "-p", "{query}", "-c", "--dangerously-skip-permissions", "--allowedTools", "Write"],
                "env": {}
            }
        self._select_available_driver()
        self.timeout = int(self.driver_config.get("timeout", 0))
        self.retries = int(self.driver_config.get("retries", 0))
        self.retry_backoff = float(self.driver_config.get("retry_backoff", 1.5))
        self.last_returncode = 0
            
        logging.info(f"🦾 Hassan Initialized: [{self.active_driver_name.upper()}] Driver")

    def _select_available_driver(self):
        command = self.driver_config.get("command")
        if command and shutil.which(command):
            return
        for name, cfg in self.drivers.items():
            cmd = cfg.get("command")
            if cmd and shutil.which(cmd):
                logging.warning(f"⚠️ Hassan Driver '{self.active_driver_name}' unavailable. Falling back to '{name}'.")
                self.active_driver_name = name
                self.driver_config = cfg
                return
        logging.error(f"❌ No available Hassan driver found (last command: {command}).")

    def prepare(self, current_task_text, persona_guidelines="", tool_registry=""):
        """Prepares system prompt files with the task block and persona."""
        if current_task_text:
            self.system_prompt_file = os.path.abspath(".night_shift_system_prompt.txt")
            with open(self.system_prompt_file, "w", encoding="utf-8") as f:
                if persona_guidelines:
                    f.write(f"PERSONA GUIDELINES:\n{persona_guidelines}\n\n")
                if tool_registry:
                    f.write(f"TOOL REGISTRY:\n{tool_registry}\n\n")
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
        if self.home_dir:
            current_env["HOME"] = self.home_dir

        logging.info(f"\n--- 🚀 Running Hassan ({self.active_driver_name}) ---")
        logging.debug(f"🦾 Hassan Command: {' '.join(_redact_cmd(cmd_list))}")
        attempt = 0
        while True:
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
                start_time = time.time()
                for line in process.stdout:
                    print(line, end='')
                    output_lines.append(line)
                    if self.timeout and (time.time() - start_time) > self.timeout:
                        process.kill()
                        self.last_returncode = 124
                        return "ERROR running Hassan: Timeout"
                process.wait()
                self.last_returncode = process.returncode
                if process.returncode != 0 and attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff ** attempt)
                    continue
                return "".join(output_lines).strip()
            except Exception as e:
                self.last_returncode = 1
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff ** attempt)
                    continue
                return f"ERROR running Hassan: {e}"

class NightShiftAgent:
    def __init__(self, mission_path="mission.yaml", log_dir=LOG_DIR, log_level="INFO", persona_map=None, reviewer_mode=False, auto_approve_plan=False, auto_approve_actions=False):
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger, self.log_file_path = setup_logging(log_dir=log_dir, log_level=level)
        self.log_dir = log_dir
        self.auto_approve_plan = auto_approve_plan
        self.auto_approve_actions = auto_approve_actions
        self.reviewer_mode = reviewer_mode
        self.persona_map = persona_map or []
        self.driver_availability_checked = False
        
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
        memory_scope = (self.settings.get("memory") or {}).get("scope", "project")
        self.memory_manager = MemoryManager(self.mission_config.get('project_path', os.getcwd()), scope=memory_scope)
        self.brain = Brain(self.settings, self.mission_config, log_dir=self.log_dir)
        self.critic = Critic(self.settings, self.mission_config)
        self.hassan = Hassan(self.settings, self.mission_config)

        if not self.brain.driver_config.get("command") or not shutil.which(self.brain.driver_config.get("command")):
            logging.error("❌ Brain driver not available. Check settings.yaml and PATH.")
        if not self.hassan.driver_config.get("command") or not shutil.which(self.hassan.driver_config.get("command")):
            logging.error("❌ Hassan driver not available. Check settings.yaml and PATH.")
        
        # Load Long-term Memories
        self.past_memories = self.memory_manager.load_memories()
        if self.past_memories:
            logging.info("📚 Long-term memories loaded. Brain is feeling experienced.")
        
        # Load Persona Guidelines
        self.personas = self.settings.get('personas', {})
        self.default_persona_name = self.mission_config.get('persona', 'general')
        self.default_persona_guidelines = self.personas.get(self.default_persona_name, "")
        self.persona_rules = self.settings.get("persona_rules", [])
        for rule in self.persona_map:
            self.persona_rules.insert(0, rule)

        if self.default_persona_guidelines:
            logging.info(f"🎭 Default Persona: [{self.default_persona_name.upper()}]")

        self.conversation_history = ""
        self.last_hassan_query = ""
        self.last_hassan_output = ""
        self.tool_registry = "\n".join(self.settings.get("tools", []))
        self.brain_output_format = (self.settings.get("brain") or {}).get("output_format", "text")
        self.task_summaries = []
        self.run_start_time = datetime.now()

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

    def _requires_approval(self, command):
        destructive_patterns = [
            r"\brm\s+-rf\b",
            r"\bgit\s+reset\b",
            r"\bgit\s+clean\b",
            r"\bdel\s+/f\b",
            r"\brmdir\b",
            r"\bshutdown\b",
            r"\breboot\b",
        ]
        return any(re.search(pat, command, re.IGNORECASE) for pat in destructive_patterns)

    def _plan_tasks(self, raw_goal, constraints):
        planner_config = self.settings.get("planner", {})
        if not planner_config.get("enabled"):
            return None
        constraints_text = "\n".join(constraints or [])
        prompt = f"""
You are a planning assistant. Break the mission into a concise list of actionable tasks.

[MISSION]
{raw_goal}

[CONSTRAINTS]
{constraints_text}

[OUTPUT]
Return ONLY valid JSON:
{{"tasks": ["task 1", "task 2", "..."]}}
"""
        response = self.brain._run_cli_command(prompt)
        if response.startswith("MISSION_FAILED"):
            return None
        try:
            data = json.loads(response)
            tasks = data.get("tasks", [])
            if isinstance(tasks, list) and all(isinstance(t, str) for t in tasks):
                return tasks
        except Exception:
            return None
        return None

    def _interpret_brain_response(self, response):
        if self.brain_output_format != "json":
            return response
        try:
            data = json.loads(response)
            status = data.get("status", "").lower()
            command = data.get("command", "")
            if status == "completed":
                return "MISSION_COMPLETED"
            return command
        except Exception:
            return response

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

    def _git_worktree_add(self, work_dir, commit_hash):
        try:
            subprocess.run(["git", "worktree", "add", "--force", work_dir, commit_hash], cwd=self.mission_config.get('project_path', os.getcwd()))
            return True
        except Exception as e:
            logging.error(f"❌ Failed to create worktree: {e}")
            return False

    def _git_worktree_remove(self, work_dir):
        try:
            subprocess.run(["git", "worktree", "remove", "--force", work_dir], cwd=self.mission_config.get('project_path', os.getcwd()))
        except Exception as e:
            logging.error(f"❌ Failed to remove worktree: {e}")

    def _apply_worktree_patch(self, work_dir, project_root):
        try:
            diff = subprocess.run(["git", "-C", work_dir, "diff"], capture_output=True, text=True)
            patch = diff.stdout
            if not patch.strip():
                return True
            apply_res = subprocess.run(["git", "-C", project_root, "apply"], input=patch, text=True)
            return apply_res.returncode == 0
        except Exception as e:
            logging.error(f"❌ Failed to apply worktree patch: {e}")
            return False

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

    def _execute_single_task(self, i, task_item, all_tasks, constraints, safety_config, reviewer_mode=False):
        """Executes a single task item (supports strings or dicts with sub_tasks)."""
        # Task-level checkpoint
        task_start_commit = self._get_git_head()
        task_block = task_item.get("text") if isinstance(task_item, dict) else self._format_task_block(task_item)
        task_start_time = datetime.now()
        
        # Isolated workspace for parallel execution
        is_parallel = self.mission_config.get('parallel', False)
        project_root = self.mission_config.get('project_path', os.getcwd())
        work_dir = project_root
        use_worktrees = self.settings.get("parallel", {}).get("use_worktrees", False) or safety_config.get("use_worktrees", False) or safety_config.get("preview_changes", False)
        created_worktree = False

        if (is_parallel or safety_config.get("preview_changes")) and use_worktrees and task_start_commit:
            work_dir = os.path.join(project_root, SQUAD_WORKSPACE_DIR, f"task_{i}")
            logging.info(f"🧩 Using git worktree for Task {i}: {work_dir}")
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
            if self._git_worktree_add(work_dir, task_start_commit):
                created_worktree = True
            else:
                work_dir = project_root

        if is_parallel and work_dir == project_root:
            work_dir = os.path.join(project_root, SQUAD_WORKSPACE_DIR, f"task_{i}")
            logging.info(f"⚡ Creating isolated workspace for Task {i}: {work_dir}")
            if os.path.exists(work_dir): shutil.rmtree(work_dir)
            # Simple clone: copy current directory excluding .night_shift and logs
            os.makedirs(work_dir, exist_ok=True)
            ignore_patterns = _load_ignore_patterns(project_root)
            for item in os.listdir(project_root):
                if item in ['.night_shift', 'logs', '.git', '__pycache__']: continue
                s = os.path.join(project_root, item)
                d = os.path.join(work_dir, item)
                if _is_ignored(s, project_root, ignore_patterns):
                    continue
                if os.path.isdir(s): shutil.copytree(s, d)
                else: shutil.copy2(s, d)
        
        task_text = task_item.get("text", task_block) if isinstance(task_item, dict) else task_block
        persona_name = task_item.get("persona_name") if isinstance(task_item, dict) else self.default_persona_name
        persona_guidelines = task_item.get("persona_guidelines") if isinstance(task_item, dict) else self.default_persona_guidelines

        logging.info(f"\n{'='*60}\n🚀 STARTING TASK {i} (Persona: {persona_name})\n{task_block}\n{'='*60}\n")
        
        if reviewer_mode:
            review_prompt = f"""
You are a code reviewer. Provide a concise review plan and key changes you would make for the task.

[TASK]
{task_block}

[CONSTRAINTS]
{constraints}
"""
            review_output = self.brain._run_cli_command(review_prompt)
            logging.info(f"🧑‍⚖️ Reviewer Mode Output:\n{review_output}")
            self.task_summaries.append({
                "task": task_block,
                "persona": persona_name,
                "status": "review_only",
                "duration_seconds": (datetime.now() - task_start_time).total_seconds()
            })
            return f"\n=== TASK {i} REVIEW ===\n{review_output}\n"

        self.hassan.prepare(current_task_text=task_block, persona_guidelines=persona_guidelines, tool_registry=self.tool_registry)
        initial_query = f"Start Task {i}: {task_block}"
        
        # Note: If parallel, hassan needs to know the correct work_dir
        orig_path = self.hassan.mission_config.get('project_path', os.getcwd())
        self.hassan.mission_config['project_path'] = work_dir
        
        task_completed = False
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
                    self.past_memories,
                    self.tool_registry,
                    self.brain_output_format
                )
                next_action = self._interpret_brain_response(next_action)
                task_history += f"\n--- 🧠 DIRECTOR DECISION ---\n{next_action}\n"

                if "capacity" in next_action or "quota" in next_action.lower():
                    self._handle_quota_limit(next_action); continue

                if next_action == "MISSION_COMPLETED":
                    qa_config = self.settings.get("qa", {})
                    if qa_config.get("run_tests"):
                        if qa_config.get("test_on_each_task", True):
                            test_command = qa_config.get("test_command")
                            if not test_command:
                                test_command = "pytest" if os.path.exists(os.path.join(self.hassan.mission_config.get('project_path', os.getcwd()), "tests")) else ""
                            if test_command:
                                logging.info(f"🧪 Running tests: {test_command}")
                                test_output = self.hassan.run(test_command)
                                task_history += f"\n--- 🧪 TEST OUTPUT ---\n{test_output}\n"
                                if self.hassan.last_returncode != 0:
                                    last_output = f"Tests failed: {test_output}"
                                    continue
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
                    self.task_summaries.append({
                        "task": task_block,
                        "persona": persona_name,
                        "status": "failed",
                        "duration_seconds": (datetime.now() - task_start_time).total_seconds()
                    })
                    return f"TASK_{i}_FAILED: {next_action}"
                
                if safety_config.get("require_approval_for_destructive") and self._requires_approval(next_action) and not self.auto_approve_actions:
                    approval = input(f"Destructive action detected. Approve? [y/N]: ").strip().lower()
                    if approval != "y":
                        logging.info("❌ Destructive action rejected by user.")
                        return f"TASK_{i}_FAILED: Destructive action rejected."

                hassan_output = self.hassan.run(next_action)
                task_history += f"\n--- 🦾 HASSAN OUTPUT ---\n{hassan_output}\n"
                last_output = hassan_output
                time.sleep(RATE_LIMIT_SLEEP)
            
            self.task_summaries.append({
                "task": task_block,
                "persona": persona_name,
                "status": "completed",
                "duration_seconds": (datetime.now() - task_start_time).total_seconds()
            })
            task_completed = True
            return task_history
        finally:
            if created_worktree:
                if safety_config.get("preview_changes") and task_completed:
                    approval = "y" if self.auto_approve_actions else input("Apply previewed changes to main workspace? [y/N]: ").strip().lower()
                    if approval == "y":
                        applied = self._apply_worktree_patch(work_dir, project_root)
                        if applied:
                            logging.info("✅ Applied worktree changes to main workspace.")
                        else:
                            logging.error("❌ Failed to apply worktree changes.")
                self._git_worktree_remove(work_dir)
            self.hassan.mission_config['project_path'] = orig_path

    def start(self):
        logging.info(f"🌙 Night Shift (v4.2) Starting with default persona: {self.default_persona_name}")
        if self.brain.driver_config.get("command") and not shutil.which(self.brain.driver_config.get("command")):
            logging.error("❌ Brain driver command not found in PATH.")
        if self.hassan.driver_config.get("command") and not shutil.which(self.hassan.driver_config.get("command")):
            logging.error("❌ Hassan driver command not found in PATH.")
        
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
        reviewer_mode = self.mission_config.get('reviewer_mode', False) or self.reviewer_mode

        planned = self._plan_tasks(raw_tasks, constraints)
        if planned:
            logging.info("🧭 Planner produced a task list.")
            if self.settings.get("planner", {}).get("require_approval", False) and not self.auto_approve_plan:
                print("Proposed plan:")
                for idx, task in enumerate(planned, 1):
                    print(f"{idx}. {task}")
                approval = input("Approve this plan? [y/N]: ").strip().lower()
                if approval != "y":
                    logging.info("❌ Plan rejected. Falling back to original tasks.")
                else:
                    tasks = planned
            else:
                tasks = planned

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
                max_workers = self.settings.get("parallel", {}).get("max_workers", len(normalized_tasks))
                if not isinstance(max_workers, int) or max_workers <= 0:
                    max_workers = len(normalized_tasks)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    results = list(executor.map(lambda x: self._execute_single_task(x[0], x[1], normalized_tasks, constraints, safety_config, reviewer_mode), enumerate(normalized_tasks, 1)))
                for res in results:
                    self.conversation_history += res
            else:
                for i, task_item in enumerate(normalized_tasks, 1):
                    res = self._execute_single_task(i, task_item, normalized_tasks, constraints, safety_config, reviewer_mode)
                    self.conversation_history += res

            qa_config = self.settings.get("qa", {})
            if qa_config.get("run_tests") and not qa_config.get("test_on_each_task", True):
                test_command = qa_config.get("test_command")
                if not test_command:
                    test_command = "pytest" if os.path.exists(os.path.join(self.hassan.mission_config.get('project_path', os.getcwd()), "tests")) else ""
                if test_command:
                    logging.info(f"🧪 Running tests: {test_command}")
                    test_output = self.hassan.run(test_command)
                    self.conversation_history += f"\n--- 🧪 TEST OUTPUT ---\n{test_output}\n"

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
            summary = {
                "started_at": self.run_start_time.isoformat(),
                "ended_at": datetime.now().isoformat(),
                "tasks": self.task_summaries,
                "parallel": is_parallel,
                "reviewer_mode": reviewer_mode
            }
            summary_path = os.path.join(self.log_dir, f"night_shift_summary_{self.run_start_time.strftime('%Y%m%d_%H%M%S')}.json")
            try:
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2)
                logging.info(f"🧾 Summary saved: {summary_path}")
            except Exception as e:
                logging.error(f"❌ Failed to write summary: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Night Shift: Brain & Hassan")
    parser.add_argument("mission_file", nargs="?", default="mission.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Validate config files and exit")
    parser.add_argument("--log-dir", default=LOG_DIR, help="Directory for log files")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--reviewer", action="store_true", help="Review-only mode (no execution)")
    parser.add_argument("--auto-approve-plan", action="store_true", help="Auto-approve planner output")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve destructive actions and previews")
    parser.add_argument("--persona-map", action="append", default=[], help="Persona rule mapping: pattern:persona (regex)")
    args = parser.parse_args()
    persona_map = []
    for mapping in args.persona_map:
        if ":" in mapping:
            pattern, persona = mapping.split(":", 1)
            persona_map.append({"pattern": pattern, "persona": persona, "flags": "i"})
    try:
        agent = NightShiftAgent(
            mission_path=args.mission_file,
            log_dir=args.log_dir,
            log_level=args.log_level,
            persona_map=persona_map,
            reviewer_mode=args.reviewer,
            auto_approve_plan=args.auto_approve_plan,
            auto_approve_actions=args.auto_approve
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)
    if args.dry_run:
        print("Configuration OK.")
        sys.exit(0)
    agent.start()
