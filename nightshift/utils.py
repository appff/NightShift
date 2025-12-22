import fnmatch
import logging
import os
import re
import shutil
from datetime import datetime

from .constants import IGNORE_FILE, LOG_DIR


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
