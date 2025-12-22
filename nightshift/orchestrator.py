import json
import logging
import os
import re
import shutil
import subprocess
import time
import sys
import shlex
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import yaml

from .agents import Brain, Critic, Hassan, MemoryManager
from .constants import LOG_DIR, RATE_LIMIT_SLEEP, SETTINGS_FILE, SQUAD_WORKSPACE_DIR
from .utils import _is_ignored, _load_ignore_patterns, setup_logging
from .validation import validate_mission_schema, validate_settings_schema


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

        if not os.path.exists(mission_path):
            sys.exit(1)

        with open(mission_path, "r", encoding="utf-8") as f:
            self.mission_config = yaml.safe_load(f)
        if self.mission_config is None:
            raise ValueError("Mission file is empty or invalid YAML")
        validate_mission_schema(self.mission_config)

        if not os.path.exists(SETTINGS_FILE):
            self.settings = {}
        else:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                self.settings = yaml.safe_load(f) or {}
        self._apply_mission_overrides()
        validate_settings_schema(self.settings)

        memory_scope = (self.settings.get("memory") or {}).get("scope", "project")
        self.memory_manager = MemoryManager(self.mission_config.get("project_path", os.getcwd()), scope=memory_scope)
        self.brain = Brain(self.settings, self.mission_config, log_dir=self.log_dir)
        self.critic = Critic(self.settings, self.mission_config)
        self.hassan = Hassan(self.settings, self.mission_config)

        if not self.brain.driver_config.get("command") or not shutil.which(self.brain.driver_config.get("command")):
            logging.error("❌ Brain driver not available. Check settings.yaml and PATH.")
        if not self.hassan.driver_config.get("command") or not shutil.which(self.hassan.driver_config.get("command")):
            logging.error("❌ Hassan driver not available. Check settings.yaml and PATH.")

        self.past_memories = self.memory_manager.load_memories()
        if self.past_memories:
            logging.info("📚 Long-term memories loaded. Brain is feeling experienced.")

        self.personas = self.settings.get("personas", {})
        self.default_persona_name = self.mission_config.get("persona", "general")
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
        self.resume_enabled = self.settings.get("resume", True)
        self.state_file = os.path.join(self.mission_config.get("project_path", os.getcwd()), ".night_shift", "state.json")
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

    def _compact_history(self, history):
        if not self.context_reduction.get("enabled"):
            return history
        head_chars = self.context_reduction.get("head_chars", 800)
        tail_chars = self.context_reduction.get("tail_chars", 2000)
        if not isinstance(head_chars, int) or head_chars < 0:
            head_chars = 800
        if not isinstance(tail_chars, int) or tail_chars < 0:
            tail_chars = 2000
        if len(history) <= (head_chars + tail_chars):
            return history
        head = history[:head_chars].rstrip()
        tail = history[-tail_chars:].lstrip()
        return f"{head}\n\n...[context trimmed]...\n\n{tail}"

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
                if target < now:
                    target += timedelta(days=1)
                target += timedelta(minutes=1)
            elif match_rel and any(match_rel.groups()):
                h, m, s = int(match_rel.group(1) or 0), int(match_rel.group(2) or 0), int(match_rel.group(3) or 0)
                target = now + timedelta(hours=h, minutes=m, seconds=s + 30)

            if not target:
                time.sleep(3600)
                return

            while True:
                remaining = (target - datetime.now()).total_seconds()
                if remaining <= 0:
                    break
                logging.info(f"💤 Waiting for quota reset... {remaining/60:.1f} minutes left.")
                time.sleep(min(1800, remaining))
        except Exception:
            time.sleep(3600)

    def _get_git_head(self):
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.mission_config.get("project_path", os.getcwd()),
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
                cwd=self.mission_config.get("project_path", os.getcwd()),
            )
            return res.returncode == 0 and bool(res.stdout.strip())
        except Exception:
            return False

    def _git_stash(self, message):
        try:
            subprocess.run(
                ["git", "stash", "push", "-u", "-m", message],
                cwd=self.mission_config.get("project_path", os.getcwd()),
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
                cwd=self.mission_config.get("project_path", os.getcwd()),
            )
            logging.info("✅ Rollback successful.")
        except Exception as e:
            logging.error(f"❌ Rollback failed: {e}")

    def _git_worktree_add(self, work_dir, commit_hash):
        try:
            subprocess.run(
                ["git", "worktree", "add", "--force", work_dir, commit_hash],
                cwd=self.mission_config.get("project_path", os.getcwd()),
            )
            return True
        except Exception as e:
            logging.error(f"❌ Failed to create worktree: {e}")
            return False

    def _git_worktree_remove(self, work_dir):
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", work_dir],
                cwd=self.mission_config.get("project_path", os.getcwd()),
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

        title = task_item.get("task") or task_item.get("goal") or task_item.get("title", "Untitled Task")
        sub_tasks = task_item.get("sub_tasks", []) or []

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
        task_start_commit = self._get_git_head()
        task_block = task_item.get("text") if isinstance(task_item, dict) else self._format_task_block(task_item)
        task_start_time = datetime.now()

        is_parallel = self.mission_config.get("parallel", False)
        project_root = self.mission_config.get("project_path", os.getcwd())
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

        logging.info(f"\n{'=' * 60}\n🚀 STARTING TASK {i} (Persona: {persona_name})\n{task_block}\n{'=' * 60}\n")

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
            self.task_summaries.append(
                {
                    "task": task_block,
                    "persona": persona_name,
                    "status": "review_only",
                    "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                }
            )
            return f"\n=== TASK {i} REVIEW ===\n{review_output}\n"

        self.hassan.prepare(current_task_text=task_block, persona_guidelines=persona_guidelines, tool_registry=self.tool_registry)
        initial_query = f"Start Task {i}: {task_block}"

        orig_path = self.hassan.mission_config.get("project_path", os.getcwd())
        self.hassan.mission_config["project_path"] = work_dir

        task_completed = False
        last_check_command = None
        last_check_output = None
        repeat_check_count = 0
        try:
            hassan_output = self.hassan.run(initial_query)
            task_history = f"\n=== TASK {i} START ===\nDirector Init: {initial_query}\nHassan Output:\n{hassan_output}\n"
            last_output = hassan_output

            while True:
                if "hit your limit" in last_output and "resets" in last_output:
                    self._handle_quota_limit(last_output)

                if re.search(r"task status:\s*completed", last_output, re.IGNORECASE) or "✅" in last_output:
                    logging.info("🤖 Hassan indicates task is complete. Forcing MISSION_COMPLETED.")
                    next_action = "MISSION_COMPLETED"
                else:
                    next_action = self.brain.think(
                        task_block,
                        str([t.get("text", t) if isinstance(t, dict) else t for t in all_tasks]),
                        constraints,
                        self._compact_history(task_history),
                        last_output,
                        persona_guidelines,
                        self.past_memories,
                        self.tool_registry,
                        self.brain_output_format,
                    )
                    next_action = self._interpret_brain_response(next_action)
                task_history += f"\n--- 🧠 DIRECTOR DECISION ---\n{next_action}\n"

                if "capacity" in next_action or "quota" in next_action.lower():
                    self._handle_quota_limit(next_action)
                    continue

                if next_action == "MISSION_COMPLETED":
                    qa_config = self.settings.get("qa", {})
                    if qa_config.get("run_tests"):
                        if qa_config.get("test_on_each_task", True):
                            test_command = qa_config.get("test_command")
                            if not test_command:
                                test_command = (
                                    "pytest"
                                    if os.path.exists(os.path.join(self.hassan.mission_config.get("project_path", os.getcwd()), "tests"))
                                    else ""
                                )
                            if test_command:
                                logging.info(f"🧪 Running tests: {test_command}")
                                test_output = self.hassan.run(test_command)
                                task_history += f"\n--- 🧪 TEST OUTPUT ---\n{test_output}\n"
                                if self.hassan.last_returncode != 0:
                                    last_output = f"Tests failed: {test_output}"
                                    continue
                    if self.critic.critic_config.get("enabled") is False:
                        logging.info("🧠 Critic disabled; Brain approving completion.")
                        verification = "APPROVED"
                    else:
                        verification = self.critic.evaluate(task_block, self._compact_history(task_history), last_output)
                    if verification.strip().upper() == "APPROVED":
                        logging.info(f"✅ Task {i} Verified and Completed!")
                        state = self._load_state()
                        completed = set(state.get("completed_indices", []))
                        completed.add(i)
                        state["completed_indices"] = sorted(completed)
                        self._save_state(state)
                        break
                    logging.info(f"🕵️‍♂️ Critic Rejected Task {i}: {verification}")
                    task_history += (
                        f"\n--- 🕵️‍♂️ CRITIC FEEDBACK (REJECTED) ---\n{verification}\n"
                        "Please address the issues mentioned above.\n-----------------------------------\n"
                    )
                    hassan_output = f"Critic feedback received: {verification}. I need to fix these issues."
                    last_output = hassan_output
                    continue

                if next_action.startswith("MISSION_FAILED"):
                    logging.error(f"❌ Task {i} Failed: {next_action}")
                    if safety_config.get("auto_rollback_on_failure"):
                        self._git_rollback(task_start_commit)
                    self.task_summaries.append(
                        {
                            "task": task_block,
                            "persona": persona_name,
                            "status": "failed",
                            "duration_seconds": (datetime.now() - task_start_time).total_seconds(),
                        }
                    )
                    return f"TASK_{i}_FAILED: {next_action}"

                if self._is_local_check_command(next_action):
                    local_output = self._run_local_check(next_action, work_dir)
                    task_history += f"\n--- 🔍 LOCAL CHECK OUTPUT ---\n{local_output}\n"
                    if next_action == last_check_command and local_output == last_check_output:
                        repeat_check_count += 1
                    else:
                        repeat_check_count = 0
                    last_check_command = next_action
                    last_check_output = local_output
                    last_output = local_output
                    if self.critic.critic_config.get("enabled") is False and repeat_check_count >= 1:
                        logging.info(f"✅ Task {i} completed after repeated local checks.")
                        break
                    continue

                if safety_config.get("require_approval_for_destructive") and self._requires_approval(next_action) and not self.auto_approve_actions:
                    approval = input("Destructive action detected. Approve? [y/N]: ").strip().lower()
                    if approval != "y":
                        logging.info("❌ Destructive action rejected by user.")
                        return f"TASK_{i}_FAILED: Destructive action rejected."

                hassan_output = self.hassan.run(next_action)
                task_history += f"\n--- 🦾 HASSAN OUTPUT ---\n{hassan_output}\n"
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
            state = self._load_state()
            completed = set(state.get("completed_indices", []))
            completed.add(i)
            state["completed_indices"] = sorted(completed)
            self._save_state(state)
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
            self.hassan.mission_config["project_path"] = orig_path

    def start(self):
        logging.info(f"🌙 Night Shift (v4.3.1) Starting with default persona: {self.default_persona_name}")
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
                cwd=self.mission_config.get("project_path", os.getcwd()),
            )
            logging.info(f"🛡️ Created backup branch (no checkout): {branch_name}")

        raw_tasks = self.mission_config.get("goal")
        if raw_tasks is None:
            raw_tasks = self.mission_config.get("task", [])
        tasks = raw_tasks if isinstance(raw_tasks, list) else [raw_tasks]
        constraints = self.mission_config.get("constraints", [])
        is_parallel = self.mission_config.get("parallel", False)
        reviewer_mode = self.mission_config.get("reviewer_mode", False) or self.reviewer_mode

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

        state = self._load_state()
        completed_indices = set(state.get("completed_indices", []))

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
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    results = list(
                        executor.map(
                            lambda x: self._execute_single_task(
                                x[0], x[1], normalized_tasks, constraints, safety_config, reviewer_mode
                            ),
                            enumerate(normalized_tasks, 1),
                        )
                    )
                for res in results:
                    self.conversation_history += res
            else:
                for i, task_item in enumerate(normalized_tasks, 1):
                    if i in completed_indices:
                        logging.info(f"⏭️ Skipping completed task {i} (resume enabled).")
                        continue
                    res = self._execute_single_task(i, task_item, normalized_tasks, constraints, safety_config, reviewer_mode)
                    self.conversation_history += res

            qa_config = self.settings.get("qa", {})
            if qa_config.get("run_tests") and not qa_config.get("test_on_each_task", True):
                test_command = qa_config.get("test_command")
                if not test_command:
                    test_command = (
                        "pytest"
                        if os.path.exists(os.path.join(self.hassan.mission_config.get("project_path", os.getcwd()), "tests"))
                        else ""
                    )
                if test_command:
                    logging.info(f"🧪 Running tests: {test_command}")
                    test_output = self.hassan.run(test_command)
                    self.conversation_history += f"\n--- 🧪 TEST OUTPUT ---\n{test_output}\n"

            logging.info("🧠 Reflecting on mission to store memories...")
            reflection_prompt = (
                "Based on this mission: "
                f"{str([t.get('text', t) if isinstance(t, dict) else t for t in normalized_tasks])}, "
                "provide 2-3 concise 'Lessons Learned' for future similar tasks. Output only the bullets."
            )
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
            if self.resume_enabled and os.path.exists(self.state_file):
                try:
                    os.remove(self.state_file)
                except Exception:
                    pass
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
                "reviewer_mode": reviewer_mode,
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

    def _is_local_check_command(self, command):
        if any(token in command for token in ["|", "&", ";", ">", "<"]):
            return False
        try:
            parts = shlex.split(command)
        except ValueError:
            return False
        if not parts:
            return False
        allowed = {"ls", "cat", "rg", "sed", "head", "tail", "stat", "wc"}
        return parts[0] in allowed

    def _run_local_check(self, command, cwd):
        try:
            parts = shlex.split(command)
            result = subprocess.run(parts, capture_output=True, text=True, cwd=cwd)
            output = result.stdout.strip()
            if result.stderr:
                output = (output + "\n" + result.stderr.strip()).strip()
            return output if output else "(no output)"
        except Exception as e:
            return f"LOCAL_CHECK_ERROR: {e}"
