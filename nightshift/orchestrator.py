import json
import logging
import os
import re
import shutil
import subprocess
import time
import sys
import shlex
import urllib.parse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import yaml

from .agents import Brain, Hassan, MemoryManager, SmartHassan
from .constants import LOG_DIR, RATE_LIMIT_SLEEP, SETTINGS_FILE, SQUAD_WORKSPACE_DIR
from .utils import _is_ignored, _load_ignore_patterns, setup_logging
from .validation import validate_mission_schema, validate_settings_schema

# --- NEW MODULES ---
from .memory import ReflexionMemory
from .context import ContextLoader
from .validation import ConfidenceChecker, SelfCheckProtocol
from .optimizer import TokenOptimizer, ContextCompressor
from .tools import SmartTools
from .mcp_client import MCPManager
from .metrics import PerformanceMetrics
# -------------------


class NightShiftAgent:
    def __init__(
        self,
        mission_path="mission.yaml",
        log_dir=LOG_DIR,
        log_level="INFO",
        persona_map=None,
        reviewer_mode=False,
        auto_approve_plan=False,
        auto_approve_actions=False,
    ):
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger, self.log_file_path = setup_logging(log_dir=log_dir, log_level=level)
        self.log_dir = log_dir
        self.auto_approve_plan = auto_approve_plan
        self.auto_approve_actions = auto_approve_actions
        self.reviewer_mode = reviewer_mode
        self.persona_map = persona_map or []
        self.driver_availability_checked = False
        self.mission_path = os.path.abspath(mission_path)

        if not os.path.exists(mission_path):
            sys.exit(1)

        with open(mission_path, "r", encoding="utf-8") as f:
            self.mission_config = yaml.safe_load(f)
        if self.mission_config is None:
            raise ValueError("Mission file is empty or invalid YAML")
        validate_mission_schema(self.mission_config)
        project_root = self.mission_config.get("project", {}).get("project_root", os.getcwd())
        self.root = os.path.abspath(os.path.expanduser(project_root))
        self.mission_lock_file = os.path.join(self.root, ".night_shift", "mission.lock")
        self._normalize_mission_config()

        if not os.path.exists(SETTINGS_FILE):
            self.settings = {}
        else:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                self.settings = yaml.safe_load(f) or {}
        self._apply_mission_overrides()
        validate_settings_schema(self.settings)

        project_root = self.mission_config.get("project", {}).get("project_root", os.getcwd())
        self.root = os.path.abspath(os.path.expanduser(project_root))
        memory_scope = (self.settings.get("memory") or {}).get("scope", "project")
        
        # --- INITIALIZE NEW MODULES ---
        self.memory_manager = MemoryManager(self.root, scope=memory_scope) # Original memory
        self.reflexion_memory = ReflexionMemory(os.path.join(self.root, ".night_shift/reflexion.jsonl"))
        personas_root = (
            self.mission_config.get("personas_root")
            or self.settings.get("personas_root")
            or os.path.join(os.path.dirname(os.path.dirname(__file__)), "personas")
        )
        self.context_loader = ContextLoader(personas_root)
        self.confidence_checker = ConfidenceChecker(self.root)
        self.self_checker = SelfCheckProtocol()
        self.token_optimizer = TokenOptimizer(self.root)
        self.context_compressor = ContextCompressor(max_chars=self.settings.get("context_reduction", {}).get("tail_chars", 2000))
        self.smart_tools = SmartTools(self.root)
        self.batch_config = self.settings.get("batch", {})
        self.batch_mode = self.batch_config.get("enabled", False)
        self.two_phase_config = self.settings.get("two_phase", {})
        self.two_phase_enabled = self.two_phase_config.get("enabled", False)
        metrics_config = self.settings.get("metrics", {})
        self.metrics = PerformanceMetrics(self.root, enabled=metrics_config.get("enabled", True))
        audit_config = self.settings.get("audit", {})
        self.audit_verify_once = audit_config.get("verify_once", True)
        self.audit_trust_hassan = audit_config.get("trust_hassan", True)
        self.audit_skip_on_high_confidence = audit_config.get("skip_on_high_confidence", True)
        
        # --- MCP INTEGRATION ---
        self.mcp_enabled = self.settings.get("mcp_enabled", True)
        self.mcp_manager = MCPManager(self.settings.get("mcp_servers", {}), root=self.root) if self.mcp_enabled else None
        if self.mcp_manager:
            self.mcp_manager.start()
        # -----------------------

        self.brain = Brain(self.settings, self.mission_config, log_dir=self.log_dir)
        hassan_settings = self.settings.get("hassan") or self.settings.get("body") or {}
        autonomy_level = hassan_settings.get("autonomy", "basic")
        self.hassan_warm_start = hassan_settings.get("warm_start", False)
        use_smart_hassan = (
            self.batch_mode
            or hassan_settings.get("batch_mode", False)
            or hassan_settings.get("auto_fix", False)
            or autonomy_level in ("moderate", "high")
        )
        self.hassan = SmartHassan(self.settings, self.mission_config) if use_smart_hassan else Hassan(self.settings, self.mission_config)

        if not self.brain.driver_config.get("command") or not shutil.which(self.brain.driver_config.get("command")):
            logging.error("❌ Brain driver not available. Check settings.yaml and PATH.")
        if not self.hassan.driver_config.get("command") or not shutil.which(self.hassan.driver_config.get("command")):
            logging.error("❌ Hassan driver not available. Check settings.yaml and PATH.")

        self.past_memories = self.memory_manager.load_memories()
        if self.past_memories:
            logging.info("📚 Long-term memories loaded. Brain is feeling experienced.")

        # Updated Persona Handling using ContextLoader
        self.default_persona_name = (
            self.mission_config.get("mission", {}).get("persona")
            or self.mission_config.get("persona")
            or "general"
        )
        self.default_persona_guidelines = self.context_loader.load_persona(self.default_persona_name)
        
        # Keep regex rules from settings for mapping patterns to names
        self.persona_rules = self.settings.get("persona_rules", [])
        for rule in self.persona_map:
            self.persona_rules.insert(0, rule)

        if self.default_persona_guidelines:
            logging.info(f"🎭 Default Persona: [{self.default_persona_name.upper()}] loaded from file.")

        self.conversation_history = ""
        self.last_hassan_query = ""
        self.last_hassan_output = ""
        
        base_tools = self.settings.get("tools", [])
        mcp_tools = self.mcp_manager.get_tool_definitions() if self.mcp_manager else ""
        self.tool_registry = "\n".join(base_tools) + "\n" + mcp_tools
        
        self.brain_output_format = (self.settings.get("brain") or {}).get("output_format", "text")
        self.task_summaries = []
        self.run_start_time = datetime.now()
        self.resume_enabled = self.settings.get("resume", True)
        self.state_file = os.path.join(self.root, ".night_shift", "state.json")
        self.context_reduction = self.settings.get("context_reduction", {})

    def _merge_dict(self, base, override):
        if not isinstance(base, dict) or not isinstance(override, dict):
            return override
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_dict(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _apply_mission_overrides(self):
        for key in ["brain", "critic", "body", "hassan"]:
            if key in self.mission_config:
                self.settings[key] = self._merge_dict(self.settings.get(key, {}), self.mission_config.get(key, {}))

    def _normalize_mission_config(self):
        changed = False
        mission = self.mission_config.get("mission", {})
        if mission.get("status") is None:
            mission["status"] = "active"
            changed = True
        if mission.get("created_at") is None:
            mission["created_at"] = datetime.now().strftime("%Y-%m-%d")
            changed = True
        if mission.get("updated_at") is None:
            mission["updated_at"] = datetime.now().strftime("%Y-%m-%d")
            changed = True
        self.mission_config["mission"] = mission

        tasks = self.mission_config.get("tasks", [])
        existing_ids = {t.get("id") for t in tasks if isinstance(t, dict) and t.get("id")}
        next_id_num = 1

        for task in tasks:
            if not isinstance(task, dict):
                continue
            
            # Auto-generate ID if missing
            if not task.get("id"):
                while f"task_{next_id_num}" in existing_ids:
                    next_id_num += 1
                new_id = f"task_{next_id_num}"
                task["id"] = new_id
                existing_ids.add(new_id)
                changed = True
            
            # Auto-set status if missing
            if "status" not in task:
                task["status"] = "todo"
                changed = True
                
            # Compatibility: copy 'task' to 'title' if title missing
            if "title" not in task and task.get("task"):
                task["title"] = task.get("task")
                changed = True
                
        if changed:
            self._save_mission_config()

    def _acquire_mission_lock(self, timeout=10):
        os.makedirs(os.path.dirname(self.mission_lock_file), exist_ok=True)
        start_time = time.time()
        while True:
            try:
                fd = os.open(self.mission_lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return fd
            except FileExistsError:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Failed to acquire mission lock.")
                time.sleep(0.1)

    def _release_mission_lock(self, fd):
        try:
            os.close(fd)
        finally:
            try:
                os.remove(self.mission_lock_file)
            except FileNotFoundError:
                pass

    def _save_mission_config(self):
        fd = self._acquire_mission_lock()
        try:
            tmp_path = f"{self.mission_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.mission_config, f, sort_keys=False, allow_unicode=True)
            os.replace(tmp_path, self.mission_path)
        finally:
            self._release_mission_lock(fd)

    def _update_task_status(self, task_id, status, summary_path=None, notes=None):
        tasks = self.mission_config.get("tasks", [])
        updated = False
        for task in tasks:
            if not isinstance(task, dict):
                continue
            if task.get("id") == task_id:
                task["status"] = status
                if summary_path:
                    task["summary_path"] = summary_path
                if notes is not None:
                    task["notes"] = notes
                updated = True
                break
        if updated:
            mission = self.mission_config.get("mission", {})
            mission["updated_at"] = datetime.now().isoformat()
            self.mission_config["mission"] = mission
            self._save_mission_config()

    def _load_state(self):
        if not self.resume_enabled or not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_state(self, state):
        if not self.resume_enabled:
            return
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _select_persona(self, task_text, override_persona=None):
        persona_name = self.default_persona_name
        
        if override_persona:
            persona_name = override_persona
        else:
            for rule in self.persona_rules:
                try:
                    flags = 0
                    if isinstance(rule.get("flags"), str) and "i" in rule.get("flags").lower():
                        flags |= re.IGNORECASE
                    if re.search(rule.get("pattern", ""), task_text, flags=flags):
                        persona_name = rule.get("persona")
                        break
                except re.error:
                    continue
        
        # Load content from file using ContextLoader
        guidelines = self.context_loader.load_persona(persona_name)
        return persona_name, guidelines

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

    def _compact_history(self, history, task_block=""):
        if not self.context_reduction.get("enabled"):
            return history
        return self.context_compressor.compress(history, task_block)

    def _plan_tasks(self, raw_goal, constraints):
        planner_config = self.settings.get("planner", {})
        if not planner_config.get("enabled"):
            return None
        constraints_text = "\n".join(constraints or [])
        
        # --- TOKEN OPTIMIZATION: Use Layer 0 Context ---
        layer0_context = self.token_optimizer.get_layer0_context()
        logging.info(self.token_optimizer.get_layer0_summary())
        
        prompt = f"""
You are a planning assistant. Break the mission into a concise list of actionable tasks.

[PROJECT CONTEXT (LAYER 0)]
{layer0_context}

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
        
        # 1. Check for explicit keywords first (Safety Net)
        if "MISSION_COMPLETED" in response:
            return "MISSION_COMPLETED"

        # 2. Try DSL Parsing (Simplified Output Format)
        # Format:
        # ACTION: <command>
        # STATUS: <status>
        action_match = re.search(r'^ACTION:\s*(.+)$', response, re.MULTILINE | re.IGNORECASE)
        status_match = re.search(r'^STATUS:\s*(.+)$', response, re.MULTILINE | re.IGNORECASE)
        
        if status_match and "completed" in status_match.group(1).lower():
            return "MISSION_COMPLETED"
        
        if action_match:
            cmd = action_match.group(1).strip()
            if cmd.lower() == "none":
                return "" # No action
            return cmd

        # 3. Try to find JSON code blocks first
        json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(json_pattern, response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                status = data.get("status", "").lower()
                command = data.get("command", "")
                if status == "completed":
                    return "MISSION_COMPLETED"
                return command
            except:
                pass # Fallback if block content isn't valid JSON

        # 3. Fallback: Heuristic search for JSON object (First '{' to Last '}')
        # Handles cases like: "Here is the plan: { "command": "..." } Good luck."
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = response[start : end + 1]
                data = json.loads(candidate)
                status = data.get("status", "").lower()
                command = data.get("command", "")
                if status == "completed":
                    return "MISSION_COMPLETED"
                return command
        except Exception:
            pass
            
        return response

    def _should_prefix_batch(self, command):
        if not self.batch_mode:
            return False
        if not command:
            return False
        stripped = command.lstrip()
        if stripped.upper().startswith("BATCH:"):
            return False
        return "&&" in command or "\n" in command

    def _map_virtual_command(self, command):
        if not command:
            return command
        stripped = command.strip()
        if not stripped.startswith("google_web_search"):
            return command
        query = ""
        query_match = re.search(r"\b(?:query|q)\s*=\s*(\".*?\"|\S+)", stripped)
        if query_match:
            query = query_match.group(1).strip().strip("\"")
        if not query:
            try:
                parts = shlex.split(stripped)
            except ValueError:
                return command
            if len(parts) < 2:
                return command
            query = " ".join(parts[1:]).strip()
        if not query:
            return command
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        return f"view {url}"

    def _should_block_brain_execution(self, command):
        if not command:
            return False
        stripped = command.strip()
        read_only_prefixes = ("read_file ", "ls", "rg ", "grep ", "find ", "glob ")
        if stripped.startswith(read_only_prefixes):
            return False
        if stripped.upper().startswith("BATCH:"):
            return True
        if stripped.startswith(("run_shell_command ", "write_file ", "edit ", "mcp_run ")):
            return True
        shell_tokens = ("&&", ";", "|", ">", "<")
        if any(token in stripped for token in shell_tokens):
            return True
        return False

    def _extract_file_targets(self, text):
        if not text:
            return []
        candidates = []
        ls_pattern = re.compile(r"^[\-dl][rwx-]{9}\S*\s+.+\s+(\S+)$", re.MULTILINE)
        for match in ls_pattern.finditer(text):
            candidates.append(match.group(1))
        read_file_pattern = re.compile(r"\bread_file\s+([^\s`]+)")
        for match in read_file_pattern.finditer(text):
            candidates.append(match.group(1))
        file_header_pattern = re.compile(r"--- FILE:\s+(.+?)\s+---")
        for match in file_header_pattern.finditer(text):
            candidates.append(match.group(1))
        filename_pattern = re.compile(r"\b[\w./-]+\.(py|md|txt|yaml|yml|json|js|ts)\b")
        for match in filename_pattern.finditer(text):
            candidates.append(match.group(0))
        deduped = []
        seen = set()
        for item in candidates:
            cleaned = item.strip().strip('"').strip("'")
            if not cleaned or cleaned.endswith("/"):
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    def _select_verification_command(self, task_block, last_output):
        candidates = self._extract_file_targets(last_output)
        if not candidates:
            candidates = self._extract_file_targets(task_block)
        if candidates:
            with_ext = [c for c in candidates if "." in os.path.basename(c)]
            preferred = with_ext[0] if with_ext else candidates[0]
            return f"read_file {shlex.quote(preferred)}"
        return "ls"

    def _normalize_plan_text(self, plan_text):
        if not plan_text:
            return plan_text
        if "google_web_search" not in plan_text:
            return plan_text
        lines = plan_text.splitlines()
        normalized = []
        query_pattern = re.compile(r"['\"]([^'\"]+)['\"]")
        for line in lines:
            if "google_web_search" not in line:
                normalized.append(line)
                continue
            queries = query_pattern.findall(line)
            if not queries:
                normalized.append(line.replace("google_web_search", "view"))
                continue
            urls = [f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}" for q in queries]
            url_text = " and ".join(f"`view {url}`" for url in urls)
            normalized.append(f"*   **Research:** Use {url_text} to gather sources.")
        return "\n".join(normalized)

    def _handle_quota_limit(self, error_message):
        logging.warning(f"🚨 Quota limit hit detected! Analyzing reset time: {error_message[:100]}...")
        try:
            # Robust regex for absolute time: resets 12pm, resets at 12:00 PM, etc.
            match_abs = re.search(r"resets\s+(?:at\s+)?(\d+(?::\d+)?\s*[ap]m)", error_message, re.IGNORECASE)
            match_rel = re.search(r"after\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?", error_message, re.IGNORECASE)
            now = datetime.now()
            target = None
            
            if match_abs:
                time_str = match_abs.group(1).strip().lower()
                # Try multiple common time formats
                for fmt in ["%I%p", "%I:%M%p", "%I %p", "%I:%M %p"]:
                    try:
                        target = datetime.strptime(time_str, fmt).replace(year=now.year, month=now.month, day=now.day)
                        break
                    except ValueError:
                        continue
                
                if target:
                    if target < now:
                        target += timedelta(days=1)
                    target += timedelta(minutes=1) # Buffer
                    
            elif match_rel and any(match_rel.groups()):
                h, m, s = int(match_rel.group(1) or 0), int(match_rel.group(2) or 0), int(match_rel.group(3) or 0)
                target = now + timedelta(hours=h, minutes=m, seconds=s + 30)

            if not target:
                logging.warning("⚠️ Could not parse exact reset time. Waiting for 1 hour by default.")
                time.sleep(3600)
                return

            wait_seconds = (target - datetime.now()).total_seconds()
            if wait_seconds > 0:
                logging.info(f"💤 Quota will reset at {target.strftime('%H:%M:%S')}. Waiting for {wait_seconds/60:.1f} minutes...")
                time.sleep(wait_seconds)
            logging.info("🌅 Quota reset period has passed. Resuming mission.")
        except Exception as e:
            logging.error(f"❌ Error in quota handling: {e}. Waiting for 10 minutes as fallback.")
            time.sleep(600)

    def _is_quota_error(self, text):
        if not text:
            return False
        patterns = [
            r"resource exhausted",
            r"ratelimitexceeded",
            r"status\s*[:=]\s*429",
            r"error\s*[:=]\s*429",
            r"quota will reset after",
            r"too many requests",
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _get_git_head(self):
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            return res.stdout.strip() if res.returncode == 0 else None
        except Exception:
            return None

    def _git_is_dirty(self):
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.root,
            )
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception:
            return False

    def _git_stash(self, message):
        try:
            subprocess.run(
                ["git", "stash", "push", "-u", "-m", message],
                cwd=self.root,
            )
        except Exception as e:
            logging.error(f"❌ Failed to stash changes: {e}")

    def _git_rollback(self, commit_hash):
        if not commit_hash:
            return
        logging.warning(f"⏪ Rolling back to commit: {commit_hash}...")
        try:
            if self._git_is_dirty():
                logging.warning("⚠️ Uncommitted changes detected. Stashing before rollback.")
                self._git_stash(f"night-shift-auto-stash-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                cwd=self.root,
            )
            logging.info("✅ Rollback successful.")
        except Exception as e:
            logging.error(f"❌ Rollback failed: {e}")

    def _git_worktree_add(self, work_dir, commit_hash):
        try:
            subprocess.run(
                ["git", "worktree", "add", "--force", work_dir, commit_hash],
                cwd=self.root,
            )
            return True
        except Exception as e:
            logging.error(f"❌ Failed to create worktree: {e}")
            return False

    def _git_worktree_remove(self, work_dir):
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", work_dir],
                cwd=self.root,
            )
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
        if isinstance(task_item, str):
            return f"Task: {task_item}"

        task_id = task_item.get("id", "UNKNOWN")
        title = task_item.get("title") or task_item.get("task") or "Untitled Task"
        sub_tasks = task_item.get("sub_tasks", []) or []

        block = f"TASK ID: {task_id}\nMAIN TASK: {title}\n"
        if sub_tasks:
            block += "SUB-TASKS:\n"
            for sub in sub_tasks:
                block += f"  - {sub}\n"
        return block

    def _normalize_task_item(self, task_item):
        if isinstance(task_item, str):
            return {"id": None, "text": f"Task: {task_item}", "persona": None, "status": "todo"}
        if isinstance(task_item, dict):
            task_id = task_item.get("id")
            text = task_item.get("title") or task_item.get("task")
            if not text:
                text = "Untitled Task"
            if task_item.get("sub_tasks"):
                block = self._format_task_block(task_item)
                return {
                    "id": task_id,
                    "text": block,
                    "persona": task_item.get("persona"),
                    "status": task_item.get("status", "todo"),
                }
            return {
                "id": task_id,
                "text": text,
                "persona": task_item.get("persona"),
                "status": task_item.get("status", "todo"),
            }
        return {"id": None, "text": str(task_item), "persona": None, "status": "todo"}

    def _execute_single_task(self, i, task_item, all_tasks, constraints, safety_config, reviewer_mode=False):
        task_block = task_item.get("text") if isinstance(task_item, dict) else self._format_task_block(task_item)
        if isinstance(task_item, dict) and task_item.get("sub_tasks"):
            sub_tasks = task_item.get("sub_tasks")
            if isinstance(sub_tasks, list) and sub_tasks:
                lines = []
                for entry in sub_tasks:
                    if isinstance(entry, str):
                        lines.append(f"- {entry}")
                    elif isinstance(entry, dict):
                        for key, value in entry.items():
                            lines.append(f"- {key}: {value}")
                sub_tasks_text = "\n".join(lines)
                task_block = f"{task_block}\n\n[SUB_TASKS]\n{sub_tasks_text}"
        task_id = task_item.get("id") if isinstance(task_item, dict) else None

        # --- 1. PRE-FLIGHT CHECK (Confidence) ---
        logging.info(f"🔎 Running Pre-Flight Check for Task {i}...")
        confidence_result = self.confidence_checker.calculate_confidence(task_block)
        logging.info(f"   Score: {confidence_result['score']} ({confidence_result['status']})")
        
        confidence_hint = ""
        if confidence_result.get('skip_verification'):
            logging.info("⚡ High confidence detected: Will hint Brain to skip redundant verification.")
            confidence_hint = "\n[SYSTEM ADVISORY]\nThis task is classified as high-confidence/deterministic. You may bypass manual 'cat' or 'ls' verification if the command output confirms success. Set status to 'completed' immediately if results are visible."
            
        if confidence_result['status'] == "RED":
            logging.warning("⚠️ Low confidence detected. Suggesting Deep Research...")
            # Ideally, we would insert a research task here. For now, we prepend a research instruction.
            task_block = f"[INSTRUCTION: Perform deep research/investigation first]\n{task_block}"
        # ----------------------------------------

        task_start_commit = self._get_git_head()
        task_start_time = datetime.now()

        is_parallel = self.mission_config.get("parallel", False)
        project_root = self.root
        work_dir = project_root
        use_worktrees = (
            self.settings.get("parallel", {}).get("use_worktrees", False)
            or safety_config.get("use_worktrees", False)
            or safety_config.get("preview_changes", False)
        )
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
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
            os.makedirs(work_dir, exist_ok=True)
            ignore_patterns = _load_ignore_patterns(project_root)
            for item in os.listdir(project_root):
                if item in [".night_shift", "logs", ".git", "__pycache__"]:
                    continue
                s = os.path.join(project_root, item)
                d = os.path.join(work_dir, item)
                if _is_ignored(s, project_root, ignore_patterns):
                    continue
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)

        persona_name = task_item.get("persona_name") if isinstance(task_item, dict) else self.default_persona_name
        persona_guidelines = task_item.get("persona_guidelines") if isinstance(task_item, dict) else self.default_persona_guidelines

        # --- Message Efficiency Mode ---
        if self.settings.get("message_efficiency"):
            logging.info("⚡ Message Efficiency Mode Active: Suppressing persona guidelines to save tokens.")
            persona_guidelines = ""
        # -------------------------------

        logging.info(f"\n{'=' * 60}\n🚀 STARTING TASK {i} (Persona: {persona_name})\n{'=' * 60}\n{task_block}\n{'=' * 60}\n")
        self.metrics.start_task(task_id or f"task_{i}", task_block, persona_name)

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
            review_metrics = self.metrics.finalize_task(
                "review_only",
                (datetime.now() - task_start_time).total_seconds(),
            )
            self.task_summaries.append(
                {
                    "task": task_block,
                    "persona": persona_name,
                    "status": "review_only",
                    "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                    "metrics": review_metrics,
                }
            )
            return f"\n=== TASK {i} REVIEW ===\n{review_output}\n"

        if task_id:
            self._update_task_status(task_id, "in_progress")
            self._save_state(
                {
                    "active_task_id": task_id,
                    "last_run_at": datetime.now().isoformat(),
                }
            )

        # --- 2. TOKEN OPTIMIZATION (Layer 0) ---
        # Inject Bootstrap context instead of raw file loading if needed
        layer0_context = self.token_optimizer.get_layer0_context()
        logging.info(self.token_optimizer.get_layer0_summary())
        self.hassan.prepare(current_task_text=task_block, persona_guidelines=persona_guidelines, tool_registry=self.tool_registry)
        
        initial_query = f"Start Task {i}: {task_block}\n\n[PROJECT CONTEXT]\n{layer0_context}"
        # ---------------------------------------

        task_completed = False
        last_check_command = None
        last_check_output = None
        repeat_check_count = 0
        verification_count = 0
        
        # Semantic Memory: Load only relevant lessons for this task
        relevant_memories = self.memory_manager.load_memories(query=task_block)
        
        try:
            if self.hassan_warm_start:
                hassan_output = self.hassan.run(initial_query, print_query=False)
                self.metrics.record_hassan_response(hassan_output)
            else:
                hassan_output = "READY"
            task_history = f"\n=== TASK {i} START ===\n⚙️ Orchestrator Init: {initial_query}\nHassan Output:\n{hassan_output}\n"
            last_output = hassan_output
            self_check_retry_count = 0  # Prevention for infinite self-check loops
            turn_count = 0

            if self.two_phase_enabled:
                plan_prompt = f"""
You are the Director. Create a concise execution plan for Hassan.
Do NOT execute anything yourself. Output ONLY the plan as bullet points.

[TASK]
{task_block}

[CONSTRAINTS]
{constraints}

[OUTPUT]
- Use 3-7 bullets.
- Use `view <url>` for any web searches (no external browser tools).
- Do NOT mention `google_web_search`. Use concrete `view https://www.google.com/search?q=...` URLs.
- For tests/commands, include the exact command Hassan should run (e.g., `python -m unittest ...`).
- Use `cat <path>` for file content checks (do not use `read_file`).
- Include explicit file outputs and verification steps for Hassan.
"""
                plan_text = self._normalize_plan_text(self.brain._run_cli_command(plan_prompt))
                if self._is_quota_error(plan_text):
                    self._handle_quota_limit(plan_text)
                    plan_text = self._normalize_plan_text(self.brain._run_cli_command(plan_prompt))
                if plan_text.startswith("MISSION_FAILED"):
                    logging.error(f"❌ Plan generation failed: {plan_text}")
                    return f"TASK_{i}_FAILED: {plan_text}"
                self.metrics.record_brain_response(plan_text)
                logging.info(f"\n--- 🧠 DIRECTOR PLAN ---\n{plan_text}")
                hassan_instruction = (
                    "Execute the following plan exactly and complete all deliverables.\n"
                    "After finishing, provide a concise summary and include evidence.\n\n"
                    "[EVIDENCE REQUIREMENTS]\n"
                    "- Files created/modified: show `ls -l <path>` and `cat <path>`.\n"
                    "- Files deleted: show `ls <path>` failure output.\n"
                    "- Commands/tests/builds: include the full command output.\n"
                    "- Git actions: show `git status -sb` and `git log -1 --stat`.\n"
                    "- Research/doc: list source URLs and include the final file contents.\n\n"
                    f"[PLAN]\n{plan_text}"
                )
                hassan_output = self.hassan.run(hassan_instruction, print_query=True)
                self.metrics.record_hassan_response(hassan_output)
                logging.info(f"\n--- 🦾 HASSAN OUTPUT ---\n{self.brain.clean_ansi(hassan_output)}")
                task_history += f"\n--- 🧠 DIRECTOR PLAN ---\n{plan_text}\n"
                task_history += f"\n--- 🦾 HASSAN OUTPUT ---\n{self.brain.clean_ansi(hassan_output)}\n"
                last_output = hassan_output
                if self.audit_trust_hassan or (self.audit_skip_on_high_confidence and confidence_result.get("skip_verification")):
                    logging.info("✅ Trust-Hassan mode: Skipping additional Brain verification.")
                    task_completed = True
                    if task_id:
                        self._update_task_status(task_id, "done")
                    self.task_summaries.append(
                        {
                            "task": task_block,
                            "persona": persona_name,
                            "status": "completed",
                            "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                            "metrics": self.metrics.finalize_task(
                                "completed",
                                (datetime.now() - task_start_time).total_seconds(),
                            ),
                        }
                    )
                    return task_history

            while True:
                turn_count += 1
                turn_phase = "START" if turn_count == 1 else "CONTINUE"
                logging.info(f"\n{'='*20} TURN {turn_count}: {turn_phase} {'='*20}")
                
                if "hit your limit" in last_output and "resets" in last_output:
                    self._handle_quota_limit(last_output)
                    last_output = "SYSTEM: Quota reset period has passed. Please continue the task."

                # Inject Reflexion Context into Brain
                preventive_rules = self.reflexion_memory.get_preventive_rules(task_block, last_output)
                if preventive_rules:
                    reflexion_context = "\n[LEARNED RULES]\n" + "\n".join(preventive_rules)
                else:
                    past_fixes = self.reflexion_memory.get_all_adopted_fixes()
                    reflexion_context = ""
                    if past_fixes:
                        reflexion_context = "\n[PAST SOLUTIONS (DO NOT REPEAT MISTAKES)]\n" + "\n".join(past_fixes)

                combined_constraints = constraints + ([confidence_hint] if confidence_hint else [])
                raw_brain_response = self.brain.think(
                    task_block,
                    str([t.get("text", t) if isinstance(t, dict) else t for t in all_tasks]),
                    combined_constraints,
                    self._compact_history(task_history, task_block),
                    last_output,
                    "", # Removed persona_guidelines: Brain acts only as Auditor/Architect
                    relevant_memories,
                    self.tool_registry,
                    output_format="json",
                    reflexion_context=reflexion_context,
                    batch_mode=self.batch_mode
                )
                if self._is_quota_error(raw_brain_response):
                    self._handle_quota_limit(raw_brain_response)
                    last_output = "SYSTEM: Quota reset period has passed. Please continue the task."
                    continue
                self.metrics.record_brain_response(raw_brain_response)
                
                # Pre-strip code fences for cleaner logging
                if self.brain_output_format == "json":
                    json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
                    match = re.search(json_pattern, raw_brain_response, re.DOTALL)
                    if match:
                        raw_brain_response = match.group(1)

                next_action = self._interpret_brain_response(raw_brain_response)
                mapped_action = self._map_virtual_command(next_action)
                if mapped_action != next_action:
                    logging.info(f"⚙️  Orchestrator Map: {next_action} -> {mapped_action}")
                    next_action = mapped_action
                if self._should_prefix_batch(next_action):
                    next_action = f"BATCH: {next_action}"
                if self._should_block_brain_execution(next_action):
                    logging.info("⚠️  Orchestrator Guard: Blocking Brain execution; enforcing audit-only verification.")
                    next_action = self._select_verification_command(task_block, last_output)
                
                # Log the final decision clearly to the console
                if next_action == "MISSION_COMPLETED":
                    logging.info("🧠 Brain Decision: ✅ MISSION COMPLETED")
                else:
                    logging.info(f"🧠 Brain Decision: 🛠️  Execute Command -> {next_action}")

                task_history += f"\n--- 🧠 DIRECTOR DECISION ---\n{next_action}\n"

                next_action_lower = next_action.lower()
                if "hit your limit" in next_action_lower and "resets" in next_action_lower:
                    self._handle_quota_limit(next_action)
                    last_output = "SYSTEM: Quota reset period has passed. Please continue the task."
                    continue

                if "capacity" in next_action or "quota" in next_action_lower:
                    self._handle_quota_limit(next_action)
                    continue

                if next_action == "MISSION_COMPLETED":
                    # ... self-check and completion logic ...
                    # Validate before accepting completion
                    self_check_result = self.self_checker.validate_completion(
                        persona_name, task_block, task_history, []
                    )
                    
                    if not self_check_result["passed"]:
                        self_check_retry_count += 1
                        if self_check_retry_count > 2:
                            logging.warning(f"⚠️ Self-Check failed {self_check_retry_count} times. Forcing completion to prevent loop.")
                            # Force pass or mark potential issues
                        else:
                            logging.warning(f"⚠️ Self-Check Failed (Attempt {self_check_retry_count}): {self_check_result['missing']}")
                            # Feedback to Brain directly via history/output, DO NOT run as command
                            failure_msg = (
                                "SYSTEM ALERT: Self-Check Failed. Missing evidence for: "
                                f"{self_check_result['missing']}. "
                                "Provide verification outputs (ls/read_file/command logs or git status/log) and retry."
                            )
                            task_history += f"\n--- 🛡️ SELF-CHECK FEEDBACK ---\n{failure_msg}\n"
                            last_output = failure_msg
                            continue # Skip hassan.run and go back to Brain
                    
                    logging.info("✅ Self-Check Passed (or forced).")
                    # --------------------------------------------
                    
                    # Proceed to completion processing
                    qa_config = self.settings.get("qa", {})
                    if qa_config.get("run_tests"):
                        if qa_config.get("test_on_each_task", True):
                            test_command = qa_config.get("test_command")
                            if not test_command:
                                test_command = (
                                    "pytest"
                                    if os.path.exists(os.path.join(work_dir, "tests"))
                                    else ""
                                )
                                if test_command:
                                    logging.info(f"🧪 Running tests: {test_command}")
                                    test_output = self.hassan.run(test_command)
                                    self.metrics.record_hassan_response(test_output)
                                    self.metrics.record_command(test_command, local_check=False, batch=False)
                                    task_history += f"\n--- 🧪 TEST OUTPUT ---\n{test_output}\n"
                                    if self.hassan.last_returncode != 0:
                                        last_output = f"Tests failed: {test_output}"
                                    
                                    # --- REFLEXION RECORDING ---
                                    # If tests fail, record it
                                    self.reflexion_memory.add_entry(
                                        error_signature=f"Test failure in Task {i}",
                                        root_cause="Automated test failure",
                                        fix="Pending fix", # We don't know the fix yet
                                        status="pending"
                                    )
                                    # ---------------------------
                                    continue
                    
                    logging.info(f"✅ Task {i} Verified and Completed!")
                    if task_id:
                        self._update_task_status(task_id, "done")
                    break

                if next_action.startswith("MISSION_FAILED"):
                    logging.error(f"❌ Task {i} Failed: {next_action}")
                    if safety_config.get("auto_rollback_on_failure"):
                        self._git_rollback(task_start_commit)
                    failure_metrics = self.metrics.finalize_task(
                        "failed",
                        (datetime.now() - task_start_time).total_seconds(),
                    )
                    self.task_summaries.append(
                        {
                            "task": task_block,
                            "persona": persona_name,
                            "status": "failed",
                            "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                            "metrics": failure_metrics,
                        }
                    )
                    if task_id:
                        self._update_task_status(task_id, "blocked", notes=next_action)
                    return f"TASK_{i}_FAILED: {next_action}"

                # --- 🚀 SMART EXECUTION LAYER (Interception) ---
                intercepted_output = None
                
                # 1. Local Observation Tools (Direct Execution)
                if self._is_local_check_command(next_action):
                    logging.info(f"⚙️  Orchestrator Intercept: Direct Observation -> {next_action}")
                    self.metrics.record_command(next_action, local_check=True, batch=False)
                    intercepted_output = self._run_local_check(next_action, work_dir)
                    task_history += f"\n--- 🔍 DIRECT OUTPUT ---\n{intercepted_output}\n"
                    verification_count += 1
                    
                    # Anti-looping for local checks
                    if next_action == last_check_command and intercepted_output == last_check_output:
                        repeat_check_count += 1
                    else:
                        repeat_check_count = 0
                    last_check_command = next_action
                    last_check_output = intercepted_output
                    
                    if repeat_check_count >= 2:
                        logging.info(f"✅ Task {i} likely complete (repeated observations).")
                        task_completed = True
                        if task_id:
                            self._update_task_status(task_id, "done")
                        self.task_summaries.append(
                            {
                                "task": task_block,
                                "persona": persona_name,
                                "status": "completed",
                                "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                                "metrics": self.metrics.finalize_task(
                                    "completed",
                                    (datetime.now() - task_start_time).total_seconds(),
                                ),
                            }
                        )
                        return task_history

                    if self.audit_verify_once and verification_count >= 2:
                        logging.info(f"✅ Task {i} likely complete (single-pass audit).")
                        task_completed = True
                        if task_id:
                            self._update_task_status(task_id, "done")
                        self.task_summaries.append(
                            {
                                "task": task_block,
                                "persona": persona_name,
                                "status": "completed",
                                "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                                "metrics": self.metrics.finalize_task(
                                    "completed",
                                    (datetime.now() - task_start_time).total_seconds(),
                                ),
                            }
                        )
                        return task_history

                # 2. Smart Mutation/Execution Tools
                # Intentionally not intercepted. Hassan should execute all mutations and free-form work.

                # If intercepted, update state and continue loop (bypass Hassan)
                if intercepted_output is not None:
                    last_output = intercepted_output
                    time.sleep(RATE_LIMIT_SLEEP)
                    continue

                # --- 🦾 STANDARD EXECUTION (Hassan) ---
                if safety_config.get("require_approval_for_destructive") and self._requires_approval(next_action) and not self.auto_approve_actions:
                    approval = input("Destructive action detected. Approve? [y/N]: ").strip().lower()
                    if approval != "y":
                        logging.info("❌ Destructive action rejected by user.")
                        return f"TASK_{i}_FAILED: Destructive action rejected."

                hassan_output = self.hassan.run(next_action)
                self.metrics.record_hassan_response(hassan_output)
                self.metrics.record_command(
                    next_action,
                    local_check=False,
                    batch=next_action.lstrip().upper().startswith("BATCH:"),
                )
                if self.audit_trust_hassan or (self.audit_skip_on_high_confidence and confidence_result.get("skip_verification")):
                    logging.info("✅ Trust-Hassan mode: Skipping additional Brain verification.")
                    task_completed = True
                    if task_id:
                        self._update_task_status(task_id, "done")
                    self.task_summaries.append(
                        {
                            "task": task_block,
                            "persona": persona_name,
                            "status": "completed",
                            "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                            "metrics": self.metrics.finalize_task(
                                "completed",
                                (datetime.now() - task_start_time).total_seconds(),
                            ),
                        }
                    )
                    return task_history
                if not hassan_output.strip():
                    hassan_output = "SYSTEM ALERT: Hassan returned an empty response. If you were trying to create a file, it might have failed silently. Please verify using 'ls' or use a different method (like the write_file tool)."
                
                # Sanitize output before storing in history to save tokens
                clean_hassan_output = self.brain.clean_ansi(hassan_output)
                task_history += f"\n--- 🦾 HASSAN OUTPUT ---\n{clean_hassan_output}\n"
                last_output = hassan_output
                time.sleep(RATE_LIMIT_SLEEP)

            self.task_summaries.append(
                {
                    "task": task_block,
                    "persona": persona_name,
                    "status": "completed",
                    "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                }
            )
            if task_id:
                self._update_task_status(task_id, "done")
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

    def start(self):
        logging.info(f"🌙 Night Shift Starting with default persona: {self.default_persona_name}")
        if self.brain.driver_config.get("command") and not shutil.which(self.brain.driver_config.get("command")):
            logging.error("❌ Brain driver command not found in PATH.")
        if self.hassan.driver_config.get("command") and not shutil.which(self.hassan.driver_config.get("command")):
            logging.error("❌ Hassan driver command not found in PATH.")

        safety_config = self.settings.get("safety", {})
        mission_start_commit = self._get_git_head()

        if safety_config.get("create_backup_branch") and mission_start_commit:
            branch_name = f"night-shift-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            subprocess.run(
                ["git", "branch", branch_name, mission_start_commit],
                cwd=self.root,
            )
            logging.info(f"🛡️ Created backup branch (no checkout): {branch_name}")

        tasks = self.mission_config.get("tasks", [])
        constraints = self.mission_config.get("constraints") or self.mission_config.get("mission", {}).get("constraints", [])
        is_parallel = self.mission_config.get("parallel", False)
        reviewer_mode = self.mission_config.get("reviewer_mode", False) or self.reviewer_mode

        if self.settings.get("planner", {}).get("enabled"):
            logging.info("ℹ️ Planner is enabled but ignored for repo-scoped missions. Define tasks in mission.yaml.")

        normalized_tasks = []
        for task_item in tasks:
            normalized = self._normalize_task_item(task_item)
            persona_name, persona_guidelines = self._select_persona(normalized["text"], normalized.get("persona"))
            normalized["persona_name"] = persona_name
            normalized["persona_guidelines"] = persona_guidelines
            normalized_tasks.append(normalized)

        logging.info(
            f"📋 Mission loaded with {len(normalized_tasks)} task(s). Mode: {'PARALLEL' if is_parallel else 'SEQUENTIAL'}"
        )

        try:
            if is_parallel:
                if os.path.exists(SQUAD_WORKSPACE_DIR):
                    shutil.rmtree(SQUAD_WORKSPACE_DIR)
                max_workers = self.settings.get("parallel", {}).get("max_workers", len(normalized_tasks))
                if not isinstance(max_workers, int) or max_workers <= 0:
                    max_workers = len(normalized_tasks)
                runnable = []
                for idx, task_item in enumerate(normalized_tasks, 1):
                    status = task_item.get("status", "todo")
                    if status in ("done", "blocked"):
                        logging.info(f"⏭️ Skipping task {task_item.get('id')} (status: {status}).")
                        continue
                    runnable.append((idx, task_item))
                if not runnable:
                    logging.info("ℹ️ No runnable tasks found.")
                    return
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    results = list(
                        executor.map(
                            lambda x: self._execute_single_task(
                                x[0], x[1], normalized_tasks, constraints, safety_config, reviewer_mode
                            ),
                            runnable,
                        )
                    )
                for res in results:
                    self.conversation_history += res
            else:
                for i, task_item in enumerate(normalized_tasks, 1):
                    status = task_item.get("status", "todo")
                    if status in ("done", "blocked"):
                        logging.info(f"⏭️ Skipping task {task_item.get('id')} (status: {status}).")
                        continue
                    res = self._execute_single_task(i, task_item, normalized_tasks, constraints, safety_config, reviewer_mode)
                    self.conversation_history += res

            qa_config = self.settings.get("qa", {})
            if qa_config.get("run_tests") and not qa_config.get("test_on_each_task", True):
                test_command = qa_config.get("test_command")
                if not test_command:
                    test_command = (
                        "pytest"
                        if os.path.exists(os.path.join(work_dir, "tests"))
                        else ""
                    )
                if test_command:
                    logging.info(f"🧪 Running tests: {test_command}")
                    test_output = self.hassan.run(test_command)
                    self.metrics.record_hassan_response(test_output)
                    self.metrics.record_command(test_command, local_check=False, batch=False)
                    self.conversation_history += f"\n--- 🧪 TEST OUTPUT ---\n{test_output}\n"

            logging.info("🧠 Reflecting on mission to store memories...")
            reflection_prompt = (
                "Based on this mission: "
                f"{str([t.get('text', t) if isinstance(t, dict) else t for t in normalized_tasks])}, "
                "provide 2-3 concise 'Lessons Learned' for future similar tasks. Output only the bullets."
            )
            insights = self.brain._run_cli_command(reflection_prompt)
            if self._is_quota_error(insights):
                self._handle_quota_limit(insights)
                insights = self.brain._run_cli_command(reflection_prompt)
            if not insights.startswith("MISSION_FAILED"):
                self.memory_manager.save_memory(insights)

            if not is_parallel:
                if safety_config.get("auto_commit_and_push"):
                    self.hassan.run("Commit and push all changes now that all tasks are completed.")
                else:
                    logging.info("ℹ️ Auto commit/push disabled. Review and commit changes manually.")
            else:
                logging.info(f"🏁 Parallel tasks finished. Check isolated workspaces in {SQUAD_WORKSPACE_DIR}")

        except KeyboardInterrupt:
            logging.warning("\n🛑 Night Shift interrupted by user. Saving logs and shutting down...")
            self.conversation_history += "\n\n[SYSTEM] Execution interrupted by user (KeyboardInterrupt).\n"
            
        finally:
            if self.resume_enabled:
                self._save_state(
                    {
                        "active_task_id": None,
                        "last_run_at": datetime.now().isoformat(),
                    }
                )
            self.hassan.cleanup()
            if hasattr(self, 'mcp_manager'):
                self.mcp_manager.stop()
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
                "reviewer_mode": reviewer_mode,
                "metrics": self.metrics.summarize_run(),
            }
            summary_path = os.path.join(
                self.log_dir, f"night_shift_summary_{self.run_start_time.strftime('%Y%m%d_%H%M%S')}.json"
            )
            try:
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2)
                logging.info(f"🧾 Summary saved: {summary_path}")
            except Exception as e:
                logging.error(f"❌ Failed to write summary: {e}")
            
            # Ensure all log buffers are flushed
            logging.shutdown()

    def _is_local_check_command(self, command):
        if any(token in command for token in ["|", "&", ";", ">", "<"]):
            return False
        try:
            parts = shlex.split(command)
        except ValueError:
            return False
        if not parts:
            return False
        # Extended list of safe, read-only tools for direct execution
        allowed = {
            "ls", "cat", "rg", "grep", "head", "tail", "stat", "wc", 
            "find", "read_file", "search_file_content", "glob",
            "view", "list", "pwd", "date", "du"
        }
        return parts[0] in allowed

    def _run_local_check(self, command, cwd):
        try:
            parts = shlex.split(command)
            cmd = parts[0]
            
            # Use SmartTools if applicable
            if cmd == "view" and len(parts) > 1:
                return self.smart_tools.view(parts[1])
            if (cmd in ["read_file", "cat"]) and len(parts) > 1:
                # Handle multiple files for cat (e.g., cat file1 file2)
                if len(parts) > 2 and cmd == "cat":
                    outputs = []
                    for p in parts[1:]:
                        outputs.append(self.smart_tools.read_file(p))
                    return "\n\n".join(outputs)
                
                # Standard single file read
                path = parts[1]
                if path.startswith("--"):
                    if len(parts) > 2: path = parts[2]
                return self.smart_tools.read_file(path)
            if cmd in ["list", "ls"]:
                target_path = "."
                if len(parts) > 1:
                    # Filter out flags like -la, -R
                    for p in parts[1:]:
                        if not p.startswith("-"):
                            target_path = p
                            break
                return self.smart_tools.list_files(target_path)
            if cmd in ["search_file_content", "rg", "grep"] and len(parts) > 1:
                pattern = ""
                search_path = "."
                # Simple heuristic to find pattern and path
                for p in parts[1:]:
                    if not p.startswith("-"):
                        if not pattern: pattern = p
                        else: search_path = p
                return self.smart_tools.search_file_content(pattern, search_path)
            if cmd == "glob" and len(parts) > 1:
                return self.smart_tools.glob(parts[1])
            
            # Fallback to standard subprocess for simple shell commands (pwd, etc.)
            result = subprocess.run(parts, capture_output=True, text=True, cwd=cwd)
            output = result.stdout.strip()
            if result.stderr:
                output = (output + "\n" + result.stderr.strip()).strip()
            return output if output else "(no output)"
        except Exception as e:
            return f"LOCAL_CHECK_ERROR: {e}"
