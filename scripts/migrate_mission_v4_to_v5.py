#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime

import yaml


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _dump_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def _is_new_schema(config):
    return isinstance(config, dict) and "project" in config and "mission" in config and "tasks" in config


def _task_title(item):
    if isinstance(item, dict):
        return item.get("task") or item.get("title") or item.get("goal")
    if isinstance(item, str):
        return item
    return None


def migrate(old_config, state_config=None):
    project_path = old_config.get("project_path", ".")
    mission_name = old_config.get("mission_name") or old_config.get("name") or "Project Mission"
    persona = old_config.get("persona")
    constraints = old_config.get("constraints", [])
    raw_goal = old_config.get("goal") or old_config.get("task") or []
    tasks = raw_goal if isinstance(raw_goal, list) else [raw_goal]

    completed_indices = set()
    if isinstance(state_config, dict):
        completed_indices = set(state_config.get("completed_indices", []))

    new_tasks = []
    for idx, item in enumerate(tasks, 1):
        title = _task_title(item) or f"Untitled Task {idx}"
        task_id = f"T-{idx:03d}"
        status = "done" if idx in completed_indices else "todo"
        entry = {
            "id": task_id,
            "title": title,
            "status": status,
            "priority": "P1",
        }
        if isinstance(item, dict):
            if item.get("persona"):
                entry["persona"] = item.get("persona")
            if item.get("sub_tasks"):
                entry["sub_tasks"] = item.get("sub_tasks")
        new_tasks.append(entry)

    new_config = {
        "project": {
            "name": mission_name,
            "project_root": project_path,
            "owner": "",
            "tags": [],
        },
        "mission": {
            "name": mission_name,
            "status": "active",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
        },
        "parallel": old_config.get("parallel", False),
        "tasks": new_tasks,
        "constraints": constraints,
    }

    if persona:
        new_config["mission"]["persona"] = persona

    for key in ["brain", "critic", "body", "hassan"]:
        if key in old_config:
            new_config[key] = old_config[key]

    return new_config


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy mission.yaml to repo-scoped schema.")
    parser.add_argument("mission_path", nargs="?", default="mission.yaml")
    parser.add_argument("--state", dest="state_path", default=None, help="Optional state.json path")
    parser.add_argument("--in-place", action="store_true", help="Overwrite mission.yaml (default)")
    args = parser.parse_args()

    if not os.path.exists(args.mission_path):
        print(f"Mission file not found: {args.mission_path}")
        sys.exit(1)

    config = _load_yaml(args.mission_path) or {}
    if _is_new_schema(config):
        print("Mission is already in repo-scoped schema. No changes made.")
        sys.exit(0)

    state_config = None
    state_path = args.state_path
    if not state_path:
        project_path = config.get("project_path", ".")
        state_path = os.path.join(project_path, ".night_shift", "state.json")
    if os.path.exists(state_path):
        state_config = _load_yaml(state_path)

    new_config = migrate(config, state_config)
    backup_path = f"{args.mission_path}.bak"
    os.replace(args.mission_path, backup_path)
    _dump_yaml(args.mission_path, new_config)
    print(f"Migrated mission saved to {args.mission_path}. Backup at {backup_path}.")


if __name__ == "__main__":
    main()
