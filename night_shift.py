#!/usr/bin/env python3
"""
Night Shift: Autonomous AI Agent Wrapper (v4.4.1 - Pure CLI & Shadow Workspace)
Target: macOS M3 (Apple Silicon)
Version: 4.4.1
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

import argparse

from nightshift.constants import LOG_DIR
from nightshift.orchestrator import NightShiftAgent


def main():
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
            auto_approve_actions=args.auto_approve,
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)
    if args.dry_run:
        print("Configuration OK.")
        sys.exit(0)
    agent.start()


if __name__ == "__main__":
    main()
