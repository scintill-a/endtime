"""Configuration constants and filesystem paths for Endtime."""
import re
from pathlib import Path

TASKS_DIR = Path.home() / ".config" / "endtime"
TASKS_FILE = TASKS_DIR / "tasks.json"
CONFIG_FILE = TASKS_DIR / "config.json"

# Precompiled regex for parsing tags like [WORK] or [DAILY]
TAG_REGEX = re.compile(r'^\[([A-Z0-9_\-\s]+)\]\s*(.*)', re.IGNORECASE)
