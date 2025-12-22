import os
import re

ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\-_]|[0-?]*[@-~])')
LOG_DIR = "logs"
LOG_FILE_TEMPLATE = os.path.join(LOG_DIR, "night_shift_log_{timestamp}.txt")
SETTINGS_FILE = "settings.yaml"
BRAIN_WORKSPACE_DIR = os.path.join(".night_shift", "brain_env")
SQUAD_WORKSPACE_DIR = os.path.join(".night_shift", "squad")
IGNORE_FILE = ".night_shiftignore"

MAX_CONTEXT_CHARS = 3000
MAX_HISTORY_CHARS = 4000
MAX_TOKENS = 1024
RATE_LIMIT_SLEEP = 2
