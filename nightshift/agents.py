import json
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta

from .constants import (
    ANSI_ESCAPE_PATTERN,
    BRAIN_WORKSPACE_DIR,
    MAX_CONTEXT_CHARS,
    MAX_HISTORY_CHARS,
)
from .utils import (
    _apply_codex_policy,
    _build_default_drivers,
    _extract_driver_block,
    _link_auth_folders,
    _redact_cmd,
)


class Brain:
    """The Intelligence Unit (Director). Decides what to do via CLI tools."""

    def __init__(self, settings, mission_config, log_dir):
        self.settings = settings
        self.mission_config = mission_config
        self.project_path = os.path.abspath(self.mission_config.get("project_path", os.getcwd()))
        self.log_dir = log_dir

        self.brain_config = self.settings.get("brain", {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.brain_config)
        if not self.active_driver_name:
            self.active_driver_name = "claude"
        if not self.drivers:
            self.drivers = _build_default_drivers("brain", self.settings)
        self.link_auth = self.brain_config.get("link_auth", True)

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
            self.driver_config = {"command": "claude", "args": ["-p", "{prompt}"]}
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
        # Remove ANSI escape codes
        text = ANSI_ESCAPE_PATTERN.sub("", text)
        
        # Strategy: Tail-based extraction for Codex
        # Codex outputs often end with a summary after "codex" or "tokens used".
        # We want to discard the noisy execution logs before that.
        
        lines = text.splitlines()
        
        # 1. Try to find the start of the final response
        cutoff_index = -1
        
        # Search from the end to find the last occurrence of markers
        for i in range(len(lines) - 1, -1, -1):
            line_stripped = lines[i].strip()
            
            # Marker: "codex" on its own line
            if re.match(r"^codex\s*$", line_stripped, re.IGNORECASE):
                cutoff_index = i + 1
                break
                
            # Marker: "tokens used" followed by a number
            if re.match(r"^tokens used\s*$", line_stripped, re.IGNORECASE):
                # Skip the "tokens used" line AND the number line following it
                if i + 1 < len(lines) and re.match(r"^\d{1,3}(?:,\d{3})*$", lines[i+1].strip()):
                    cutoff_index = i + 2
                else:
                    cutoff_index = i + 1
                break

        # If a marker was found, keep only content after it
        if cutoff_index != -1 and cutoff_index < len(lines):
            lines = lines[cutoff_index:]

        # 2. Apply standard line-based filtering to whatever remains
        # (This handles other noise like "thinking", "mcp startup", etc. if they appear in the tail)
        noise_patterns = [
            r"^tokens used\s*$",
            r"^\d{1,3}(?:,\d{3})*$",
            r"^thinking\s*$",
            r"^\*\*Preparing.*$",
            r"^codex\s*$",
            r"^mcp startup.*$",
            r"^--------\s*$",
            r"^workdir:.*$",
            r"^model:.*$",
            r"^provider:.*$",
            r"^approval:.*$",
            r"^sandbox:.*$",
            r"^reasoning.*$",
            r"^session id:.*$",
            r"^OpenAI Codex.*$",
            # Add execution success logs
            r".*succeeded in \d+ms:$",
        ]
        
        cleaned_lines = []
        for line in lines:
            line_stripped = line.strip()
            
            # Stop processing if we hit a git diff
            if line_stripped.startswith("diff --git"):
                cleaned_lines.append("\n[... file diff content trimmed for brevity ...]")
                break
                
            is_noise = False
            for pattern in noise_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_noise = True
                    break
            if not is_noise:
                cleaned_lines.append(line)
                
        return "\n".join(cleaned_lines).strip()

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
        if base_cmd == "codex":
            args_template = _apply_codex_policy(base_cmd, args_template, self.brain_config)

        cmd_list = [base_cmd]
        for arg in args_template:
            val = arg.replace("{prompt}", prompt)
            if val:
                cmd_list.append(val)

        logging.info(f"🧠 Brain Thinking via {base_cmd}...")
        logging.debug(f"🧠 Brain Command: {' '.join(_redact_cmd(cmd_list))}")

        brain_env = os.environ.copy()
        # brain_env["HOME"] = self.brain_env_dir  <-- DISABLED: Inherit real HOME for auth

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
                    timeout=self.timeout,
                )

                if process.returncode != 0:
                    error_msg = process.stderr.strip()
                    logging.error(f"🧠 Brain CLI Error ({process.returncode}): {error_msg}")
                    if attempt < self.retries:
                        attempt += 1
                        time.sleep(self.retry_backoff**attempt)
                        continue
                    return f"MISSION_FAILED: Brain CLI Error - {error_msg}"

                return process.stdout.strip()

            except subprocess.TimeoutExpired:
                logging.error(f"🧠 Brain CLI Timeout ({self.timeout}s expired).")
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff**attempt)
                    continue
                return "MISSION_FAILED: Brain CLI Timeout"
            except Exception as e:
                logging.error(f"🧠 Brain Execution Exception: {e}")
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff**attempt)
                    continue
                return f"MISSION_FAILED: {e}"

    def think(
        self,
        current_task_block,
        total_mission_context,
        constraints,
        conversation_history,
        last_hassan_output,
        persona_guidelines="",
        past_memories="",
        tool_registry="",
        output_format="text",
    ):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        constraints_text = "\n".join(constraints) if isinstance(constraints, list) else str(constraints)
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
You are a STRICT, NON-CONVERSATIONAL logic engine.
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

[DECISION LOGIC & SCOPE ENFORCEMENT]
1. **Analyze Completion:** Compare [LAST HASSAN OUTPUT] against [CURRENT ACTIVE TASK HIERARCHY].
2. **Hybrid Observation:** You can use read-only tools (`ls`, `cat`, `rg`, `grep`, `read_file`, `glob`) for INSTANT feedback. These run locally and do not consume a worker turn.
3. **Ignore Extensions:** If Hassan has completed the core requirements but suggests optional expansions (e.g., "I can also do X", "Would you like charts?"), YOU MUST IGNORE THEM. Do not expand the scope.
4. **Declare Completion:** If the core task requirements are met, output exactly: "MISSION_COMPLETED".
5. **Next Step:** If and ONLY IF the task is incomplete, output the next specific CLI command.

[INSTRUCTIONS]
1. Focus ONLY on the [CURRENT ACTIVE TASK HIERARCHY].
2. Analyze the [CONSTRAINTS], [PERSONA GUIDELINES], and [LAST HASSAN OUTPUT].
3. Determine the NEXT single, specific, and actionable command/query for Hassan.
4. If ALL parts of the [CURRENT ACTIVE TASK HIERARCHY] are complete, reply exactly: "MISSION_COMPLETED".
{output_instruction}

[CRITICAL RULE]
- Keep commands CONCISE.
- Do NOT repeat the exact same command if it failed.

[FINAL WARNING]
Your response is piped directly to a shell. Do NOT include any conversational filler (e.g., "Okay", "I will", "Here is").
Do NOT explain your reasoning.
Output ONLY the raw command string or "MISSION_COMPLETED".
"""
        if format_section:
            prompt += format_section

        log_entry = f"\n{'=' * 80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'=' * 80}\n{prompt}\n"
        self._log_brain_activity(log_entry)

        response_text = self._run_cli_command(prompt)
        logging.info(f"--- 🧠 BRAIN RESPONSE ---\n{response_text}\n--- END RESPONSE ---")
        self._log_brain_activity(
            f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-' * 80}\n{response_text}\n"
        )
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

    def load_memories(self, query=None):
        """Returns the content of the memory file, optionally filtered by relevance to a query."""
        memories = []
        files = []
        if self.scope in ("project", "both"):
            files.append(self.project_memory_file)
        if self.scope in ("global", "both"):
            files.append(self.global_memory_file)
            
        all_content = ""
        for path in files:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            all_content += "\n\n" + content
                except Exception:
                    continue
        
        all_content = all_content.strip()
        if not all_content or not query:
            return all_content

        # Simple RAG-lite: Keyword-based relevance filtering
        # Memory files use "### YYYY-MM-DD" headers to separate entries.
        sections = re.split(r"(?=### \d{4}-\d{2}-\d{2})", all_content)
        sections = [s.strip() for s in sections if s.strip()]
        
        if len(sections) <= 3:
            return all_content

        query_words = set(re.findall(r"\w+", query.lower()))
        scored_sections = []
        for section in sections:
            section_words = set(re.findall(r"\w+", section.lower()))
            score = len(query_words.intersection(section_words))
            scored_sections.append((score, section))
            
        # Sort by score descending and take top 3
        scored_sections.sort(key=lambda x: x[0], reverse=True)
        top_sections = [s[1] for s in scored_sections[:3] if s[0] > 0]
        
        if not top_sections:
            return "" # Or return generic if preferred
            
        return "\n\n---\n".join(top_sections).strip()

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
        self.project_path = os.path.abspath(self.mission_config.get("project_path", os.getcwd()))

        self.critic_config = self.settings.get("critic", {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.critic_config)
        if not self.active_driver_name:
            self.active_driver_name = "gemini"
        if not self.drivers:
            self.drivers = _build_default_drivers("critic", self.settings)
        self.active_driver_names = self.critic_config.get("active_drivers", [])
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

        if self.critic_config.get("enabled") is False:
            logging.info("🕵️‍♂️ Critic Disabled")
        else:
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
                cmd_list = [driver_config["command"]]
                args_template = driver_config.get("args", [])
                if driver_config.get("command") == "codex":
                    args_template = _apply_codex_policy(driver_config.get("command"), args_template, self.critic_config)
                for arg in args_template:
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
                    timeout=self.timeout,
                )
                response = process.stdout.strip()
                if process.returncode != 0 and attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff**attempt)
                    continue
                return response
            except Exception as e:
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff**attempt)
                    continue
                logging.error(f"🕵️‍♂️ Critic Error: {e}")
                return "APPROVED"

    def evaluate(self, task_block, history, last_output):
        """Evaluates Hassan's work against the task hierarchy."""
        if self.critic_config.get("enabled") is False:
            return "APPROVED"
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
        self.hassan_config = settings.get("body", {}) or settings.get("hassan", {})
        self.active_driver_name, self.drivers = _extract_driver_block(self.hassan_config)
        if not self.active_driver_name:
            self.active_driver_name = "claude"
        if not self.drivers:
            self.drivers = _build_default_drivers("body", settings)
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
                "args": [
                    "--system-prompt-file",
                    "{system_prompt_file}",
                    "-p",
                    "{query}",
                    "-c",
                    "--dangerously-skip-permissions",
                    "--allowedTools",
                    "Write",
                ],
                "env": {},
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
                if self.active_driver_name == "gemini":
                    f.write(
                        "GEMINI TOOLING NOTE:\n"
                        "- Use only tools that are explicitly available in this runtime.\n"
                        "- If a tool is missing, do NOT call it. Ask for an alternative or provide manual steps.\n"
                        "- Prefer these when relevant: read_file, glob, search_file_content, write_todos, save_memory.\n"
                        "- If file edits are required, provide exact edit instructions instead of calling non-existent tools.\n\n"
                    )
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
        if not query:
            return "ERROR: Empty query."

        base_cmd = self.driver_config.get("command", "claude")
        args_template = self.driver_config.get("args", [])
        if base_cmd == "codex":
            args_template = _apply_codex_policy(base_cmd, args_template, self.hassan_config)
        if self.active_driver_name == "gemini":
            query_placeholders = {"{query}", "{system_prompt_file}"}
            has_query_placeholder = any(
                any(placeholder in arg for placeholder in query_placeholders)
                for arg in args_template
                if isinstance(arg, str)
            )
            if not has_query_placeholder:
                return "ERROR: Gemini args must include '{query}' so the task is passed to the CLI."
        cmd_list = [base_cmd]

        for arg in args_template:
            val = arg.replace("{query}", query)
            val = val.replace("{system_prompt_file}", self.system_prompt_file or "")
            if val:
                cmd_list.append(val)

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
                    cwd=self.mission_config.get("project_path", os.getcwd()),
                    env=current_env,
                    bufsize=1,
                )
                output_lines = []
                start_time = time.time()
                for line in process.stdout:
                    print(line, end="")
                    output_lines.append(line)
                    if self.timeout and (time.time() - start_time) > self.timeout:
                        process.kill()
                        self.last_returncode = 124
                        return "ERROR running Hassan: Timeout"
                process.wait()
                self.last_returncode = process.returncode
                if process.returncode != 0 and attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff**attempt)
                    continue
                return "".join(output_lines).strip()
            except Exception as e:
                self.last_returncode = 1
                if attempt < self.retries:
                    attempt += 1
                    time.sleep(self.retry_backoff**attempt)
                    continue
                return f"ERROR running Hassan: {e}"
