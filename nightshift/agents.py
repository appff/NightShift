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
        
        # Robust root detection: Only use project_root
        project_root = self.mission_config.get("project", {}).get("project_root")
        self.root = os.path.abspath(os.path.expanduser(project_root or os.getcwd()))
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
            self.brain_env_dir = os.path.join(self.root, BRAIN_WORKSPACE_DIR)
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
            # Ollama / Local LLM noise
            r"^success\s*$",
            r"^loading model.*$",
            r"^.*\[\d+%\].*$",
            r"^.*⠋.*$",
            r"^.*⠙.*$",
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

        logging.info(f"🧠 Brain({self.active_driver_name.capitalize()}) Thinking via {base_cmd}...")
        logging.debug(f"🧠 Brain Command: {' '.join(_redact_cmd(cmd_list))}")

        brain_env = os.environ.copy()
        # brain_env["HOME"] = self.brain_env_dir  <-- DISABLED: Inherit real HOME for auth

        attempt = 0
        while True:
            try:
                # Special handling for Ollama to avoid stderr pollution (loading logs)
                is_ollama = "ollama" in base_cmd.lower()
                
                process = subprocess.run(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, # Capture separately
                    text=True,
                    cwd=self.root,
                    env=brain_env,
                    check=False,
                    timeout=self.timeout,
                )

                if process.returncode != 0:
                    # Capture both stderr and stdout as some CLIs output errors to stdout
                    raw_stderr = process.stderr.strip()
                    raw_stdout = process.stdout.strip()
                    
                    # Combine and handle newlines to prevent log truncation
                    error_msg = raw_stderr if raw_stderr else raw_stdout
                    if not error_msg:
                        error_msg = f"Exit code {process.returncode} (No output)"
                    
                    # Replace newlines with a visible separator for single-line loggers
                    safe_error_msg = error_msg.replace("\n", " | ")
                    
                    logging.error(f"🧠 Brain CLI Error ({process.returncode}): {safe_error_msg}")
                    if attempt < self.retries:
                        attempt += 1
                        time.sleep(self.retry_backoff**attempt)
                        continue
                    return f"MISSION_FAILED: Brain CLI Error - {safe_error_msg}"

                # Success case
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
        reflexion_context="",
    ):
        clean_output = self.clean_ansi(last_hassan_output)[-MAX_CONTEXT_CHARS:]
        constraints_text = "\n".join(constraints) if isinstance(constraints, list) else str(constraints)
        
        # Determine Toolset based on Driver Capability
        # Local LLMs need "Smart Tools" (High-level python wrappers)
        # SOTA LLMs (Claude/GPT-4) prefer raw shell power
        is_local_llm = any(name in self.active_driver_name.lower() for name in ["deepseek", "qwen", "llama", "ollama"])
        
        if is_local_llm:
            core_tools = """
- view <path_or_url>: Reads a local file OR a web URL (auto-cleaned).
- list <path>: Lists files in a directory.
- edit <path> <old_text> <new_text>: Replaces exact text in a file.
- run_shell_command <command>: Executes any other shell command.

IMPORTANT:
- Use `view` for BOTH local files and remote websites.
- Use `edit` for stable file modifications. It requires the EXACT text to replace.
- DO NOT invent flags for `night_shift.py`.
"""
        else:
            # Standard toolset for smart models
            core_tools = """
- read_file: Reads a file from the local filesystem.
- write_file: Writes content to a file.
- run_shell_command: Executes a shell command (ls, grep, find, curl, etc.).
- glob: Finds files matching a pattern.
"""

        tools_section = f"\n[AVAILABLE TOOLS]\n{core_tools}\n{tool_registry}\n" 

        format_section = ""
        if output_format == "json":
            format_section = """
[OUTPUT FORMAT]
You must output ONLY a single valid JSON object.
DO NOT use markdown code blocks (e.g., ```json).
DO NOT include any explanations, reasoning, or conversational text.
Your entire response must be parseable by `json.loads()`.

Required Schema:
{"command": "<next CLI command string>", "status": "continue"}
OR
{"command": "", "status": "completed"}
"""

        if persona_guidelines:
            persona_section = f"\n[WORKER (HASSAN) PERSONA & EXPERTISE]\nYour Worker (Hassan) is currently acting as a specialized agent with the following expertise/persona:\n{persona_guidelines}\n\nAs the Director, you must ensure Hassan utilizes this expertise correctly while you maintain objective oversight.\n"
        else:
            persona_section = "\n[DIRECTOR CORE IDENTITY]\nYou are currently operating in your pure Auditor/Architect mode. You must apply rigorous logic, structural integrity checks, and precise verification to all of Hassan's actions without being influenced by a specific domain persona.\n"

        memory_section = f"\n[PAST MEMORIES / LESSONS LEARNED]\n{past_memories}\n" if past_memories else ""
        reflexion_section = f"\n{reflexion_context}\n" if reflexion_context else ""

        # --- DYNAMIC THINKING STRATEGY ---
        thinking_budget = self.brain_config.get("thinking_budget", 5)
        thinking_strategy = self.brain_config.get("thinking_strategy", "balanced")
        
        strategy_prompts = {
            "concise": "Minimize thinking steps. Use sequential_thinking ONLY for high-risk architectural decisions.",
            "balanced": "Scale thinking based on complexity. For routine tasks, be direct. For novel or complex logic, use sequential_thinking moderately.",
            "thorough": "Prioritize correctness over speed. Use sequential_thinking proactively for all non-trivial logic."
        }
        selected_strategy = strategy_prompts.get(thinking_strategy, strategy_prompts["balanced"])

        cognitive_strategy = f"""
[COGNITIVE STRATEGY (AUTONOMOUS TOOL USAGE)]
- STRATEGY: {selected_strategy}
- BUDGET: Do not exceed {thinking_budget} thinking steps for this turn.
- If a task is complex or requires multi-step planning, you may use 'sequential_thinking' tools to explore logic before issuing commands.
- If you lack specific project knowledge, check 'serena' memory tools or 'context7' documentation before guessing.
- Save critical architectural insights using memory tools to ensure project continuity.
"""

        output_instruction = "5. Output ONLY the command string."
        if output_format == "json":
            output_instruction = "5. Output ONLY raw JSON. Start with { and end with }."

        prompt = f"""
You are the "Director" of an autonomous coding session.
You are a STRICT, NON-CONVERSATIONAL logic engine.
Regardless of the Worker's persona, YOUR identity is a high-level Auditor and Architect.
Your "Hassan" (Worker) is a CLI tool that executes your commands.

[LANGUAGE & REASONING]
1. **Internal Reasoning**: You SHOULD think in English for the best logic and reasoning performance.
2. **Context Understanding**: If the [CURRENT ACTIVE TASK HIERARCHY] or [OVERALL MISSION CONTEXT] is in a non-English language (e.g., Korean), you MUST understand and respect it.
3. **Artifact Generation**: If the task requires writing content in a specific language (e.g., "Write a report in Korean"), ensure your commands to Hassan explicitly preserve that language requirement.

{cognitive_strategy}
{persona_section}
{memory_section}
{reflexion_section}

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

{tools_section}

[DECISION LOGIC & STRICT EVIDENCE CHECK]
1. **EVIDENCE CHECK (CRITICAL)**: Look at [CONVERSATION HISTORY]. Do you see **PHYSICAL EVIDENCE** of completion?
   - **File Tasks**: Did you see the *actual content* of created/modified files (either via `read_file`/`view` OR displayed within the shell command used to create/update them)?
   - **Action Tasks**: Did you see a *verification command output* (e.g., `curl` response, `ps` output, `pytest` logs, `grep` matches) proving success?
   - **NO (Summary Only)**: You see only Hassan's claims without the raw results. You MUST command a verification step. Do NOT finish.
   - **YES (Visible Evidence)**: Proceed to step 2.

2. **VERIFICATION**: Compare the *visible evidence* against [CONSTRAINTS] and [CURRENT ACTIVE TASK HIERARCHY].
   - If the evidence shows errors, wrong language, or missing info: Command Hassan to fix it.
   - If the evidence confirms success: Proceed to step 3.

3. **COMPLETION**: Set "status": "completed" ONLY IF you have physically verified the results in step 1.

4. **Ignore Extensions**: If Hassan suggests optional expansions (e.g., "I can also do X"), IGNORE THEM. Focus only on the main task.

5. **Format**: Output ONLY the raw JSON object.

6. **Anti-Looping Rule**: If you find yourself issuing the same verification command (like `cat` or `read_file`) more than twice on the same files without making progress, assume you have enough information and proceed to the next logical step (e.g., declaring completion or fixing a different problem).

[INSTRUCTIONS]
1. Focus ONLY on the [CURRENT ACTIVE TASK HIERARCHY].
2. Analyze the [CONSTRAINTS] and [LAST HASSAN OUTPUT].
3. Determine the NEXT single, specific, and actionable command/query for Hassan.
4. If ALL parts of the [CURRENT ACTIVE TASK HIERARCHY] are complete AND you have physically verified the results in Step 1, set status to "completed".
{output_instruction}

[CRITICAL RULE]
- Keep commands CONCISE.
- Do NOT repeat the exact same command if it failed.

[FINAL WARNING]
Your response is piped directly to a parser.
Any text outside the JSON object will cause a system crash.
Output ONLY the raw JSON string.
"""
        if format_section:
            prompt += format_section

        log_entry = f"\n{'=' * 80}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN REQUEST\n{'=' * 80}\n{prompt}\n"
        self._log_brain_activity(log_entry)

        logging.info(f"🧠 Brain({self.active_driver_name.capitalize()}) Thinking via {self.driver_config.get('command', 'unknown')} (Context: {len(prompt)} chars)...")
        response_text = self._run_cli_command(prompt)
        
        # Filter out <think>...</think> blocks from Reasoning Models (e.g., DeepSeek R1)
        response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
        
        # PRIORITY CHECK: If MISSION_COMPLETED is anywhere in the text, treat it as done.
        # This handles cases where models say "Okay, I am done. MISSION_COMPLETED"
        if "MISSION_COMPLETED" in response_text:
            response_text = "MISSION_COMPLETED"
        
        # Clean up code fences for output
        if output_format == "json":
            json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
            match = re.search(json_pattern, response_text, re.DOTALL)
            if match:
                response_text = match.group(1)

        logging.debug(f"--- 🧠 BRAIN RESPONSE ---\n{response_text}\n--- END RESPONSE ---")
        logging.info("🧠 Brain has formulated a plan.")
        self._log_brain_activity(
            f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BRAIN RESPONSE\n{'-' * 80}\n{response_text}\n"
        )
        return response_text


class MemoryManager:
    """Handles long-term memory (lessons learned) for the Brain."""

    def __init__(self, root, scope="project"):
        self.scope = scope
        self.project_memory_file = os.path.join(root, ".night_shift", "memories.md")
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
        
        self.use_real_home = self.hassan_config.get("use_real_home", False)
        self.home_dir = None

        if self.use_real_home:
            logging.warning("⚠️ Hassan is configured to use the REAL SYSTEM HOME directory. Sandbox isolation is disabled.")
        else:
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

    def run(self, query, print_query=True):
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

        if print_query:
            logging.info(f"\n--- 🚀 Running Hassan ({self.active_driver_name}) ---\n> Command: {query}")
        else:
            logging.info(f"\n--- 🚀 Running Hassan ({self.active_driver_name}) ---")

        logging.debug(f"🦾 Hassan Command: {' '.join(_redact_cmd(cmd_list))}")
        attempt = 0
        while True:
            try:
                project_root = self.mission_config.get("project", {}).get("project_root")
                cwd = os.path.abspath(os.path.expanduser(project_root or os.getcwd()))
                
                process = subprocess.Popen(
                    cmd_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=cwd,
                    env=current_env,
                    bufsize=1,
                )
                output_lines = []
                start_time = time.time()
                for line in process.stdout:
                    # Removed live printing to keep console clean
                    # print(line, end="") 
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
