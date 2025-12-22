import os

from .utils import _extract_driver_block


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
        for key in [
            "auto_rollback_on_failure",
            "create_backup_branch",
            "auto_commit_and_push",
            "require_approval_for_destructive",
            "preview_changes",
            "use_worktrees",
        ]:
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

    context_reduction = settings.get("context_reduction")
    if context_reduction is not None and not isinstance(context_reduction, dict):
        errors.append("'context_reduction' must be a dictionary")
    elif isinstance(context_reduction, dict):
        if "enabled" in context_reduction and not isinstance(context_reduction.get("enabled"), bool):
            errors.append("'context_reduction.enabled' must be a boolean")
        if "head_chars" in context_reduction and not isinstance(context_reduction.get("head_chars"), int):
            errors.append("'context_reduction.head_chars' must be an integer")
        if "tail_chars" in context_reduction and not isinstance(context_reduction.get("tail_chars"), int):
            errors.append("'context_reduction.tail_chars' must be an integer")

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
    has_goal = bool(mission_config.get("goal"))
    has_task = bool(mission_config.get("task"))
    if not has_goal and not has_task:
        raise ValueError("Mission must have a 'goal'")

    goal = mission_config.get("goal") or mission_config.get("task")
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

    for key in ["brain", "critic", "body", "hassan"]:
        if key in mission_config and not isinstance(mission_config.get(key), dict):
            raise ValueError(f"'{key}' must be a dictionary when provided")
