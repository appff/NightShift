import fnmatch
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime

from .constants import IGNORE_FILE, LOG_DIR

DEFAULT_DRIVER_PRESETS = {
    "claude": {
        "command": "claude",
        "roles": {
            "brain": ["-p", "{prompt}", "--dangerously-skip-permissions"],
            "critic": ["-p", "{prompt}", "--dangerously-skip-permissions"],
            "body": [
                "--system-prompt-file",
                "{system_prompt_file}",
                "-p",
                "{query}",
                "-c",
                "--dangerously-skip-permissions",
                "--allowedTools",
                "Write",
            ],
        },
    },
    "gemini": {
        "command": "gemini",
        "roles": {
            "brain": ["-p", "{prompt}"],
            "critic": ["-p", "{prompt}"],
            "body": ["-p", "{query}"],
        },
    },
    "codex": {
        "command": "codex",
        "roles": {
            "brain": ["exec", "--full-auto", "{prompt}"],
            "critic": ["exec", "--full-auto", "{prompt}"],
            "body": ["exec", "--dangerously-bypass-approvals-and-sandbox", "{query}"],
        },
    },
}

_CODEX_HELP_CACHE = {}


def setup_logging(log_dir=LOG_DIR, log_level=logging.INFO):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.path.join(log_dir, f"night_shift_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

    logger = logging.getLogger()
    logger.setLevel(log_level)

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter("%(message)s")
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
    reserved_keys = {
        "active_driver",
        "active_drivers",
        "voting",
        "timeout",
        "retries",
        "retry_backoff",
        "output_format",
        "home_dir",
        "link_auth",
        "strictness",
        "enabled",
        "approval",
        "sandbox",
    }
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


def _merge_dict(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _get_driver_presets(settings):
    presets = DEFAULT_DRIVER_PRESETS
    overrides = settings.get("driver_presets")
    if isinstance(overrides, dict):
        presets = _merge_dict(presets, overrides)
    return presets


def _build_default_drivers(role, settings):
    presets = _get_driver_presets(settings)
    drivers = {}
    for name, preset in presets.items():
        if not isinstance(preset, dict):
            continue
        role_args = (preset.get("roles") or {}).get(role)
        if not role_args:
            continue
        drivers[name] = {
            "command": preset.get("command", name),
            "args": list(role_args),
            "env": {},
        }
    return drivers


def _get_codex_help(command):
    cached = _CODEX_HELP_CACHE.get(command)
    if cached is not None:
        return cached
    try:
        result = subprocess.run(
            [command, "exec", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        help_text = (result.stdout or "") + (result.stderr or "")
    except Exception:
        help_text = ""
    _CODEX_HELP_CACHE[command] = help_text
    return help_text


def _codex_supports_flag(command, flag_name):
    help_text = _get_codex_help(command)
    return flag_name in help_text


def _apply_codex_policy(command, args_template, role_config):
    if not isinstance(args_template, list):
        return args_template
    args = list(args_template)
    if "--dangerously-bypass-approvals-and-sandbox" in args:
        return args

    approval = None
    sandbox = None
    if isinstance(role_config, dict):
        approval = role_config.get("approval")
        sandbox = role_config.get("sandbox")

    if approval and "-a" not in args and "--ask-for-approval" not in args:
        if _codex_supports_flag(command, "--ask-for-approval") or _codex_supports_flag(command, "-a"):
            args.extend(["--ask-for-approval", str(approval)])
        else:
            logging.warning("⚠️ Codex CLI does not support approval flags; skipping 'approval' setting.")
    if sandbox and "--sandbox" not in args:
        if _codex_supports_flag(command, "--sandbox"):
            args.extend(["--sandbox", str(sandbox)])
        else:
            logging.warning("⚠️ Codex CLI does not support sandbox flags; skipping 'sandbox' setting.")
    return args


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


def _is_ignored(path, root_path, patterns):
    rel_path = os.path.relpath(path, root_path)
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
            return True
    return False


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
