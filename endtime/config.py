"""Configuration constants and filesystem paths for Endtime."""
import os
import re
from pathlib import Path

_custom_dir = os.environ.get("ENDTIME_DATA_DIR")
if _custom_dir:
    TASKS_DIR = Path(_custom_dir)
else:
    TASKS_DIR = Path.home() / ".config" / "endtime"

TASKS_FILE = TASKS_DIR / "tasks.json"
CONFIG_FILE = TASKS_DIR / "config.json"

# Precompiled regex for parsing tags like [WORK] or [DAILY]
TAG_REGEX = re.compile(r'^\[([A-Z0-9_\-\s]+)\]\s*(.*)', re.IGNORECASE)

# Precompiled regex for parsing inline schedule tokens like @14:30 or @tomorrow 09:00 or @in 15m
INLINE_SCHEDULE_REGEX = re.compile(
    r'(?:^|\s)@((?:in\s+\d+\s*[a-zA-Z]+|\+\d+\s*[a-zA-Z]+|\d+\s*(?:s|sec|secs|m|min|mins|h|hr|hrs|d|days)|(?:tomorrow|tmrw|today|tonight)(?:\s+[0-9]{1,2}(?::[0-9]{2})?(?:[ap]m)?)?|[0-9]{1,2}:[0-9]{2}(?:[ap]m)?|[0-9]{1,2}(?:[ap]m)|[0-9]{4}-[0-9]{2}-[0-9]{2}(?:\s+[0-9]{1,2}:[0-9]{2})?|[a-zA-Z0-9:\-\+\.]+))(?:\s|$)',
    re.IGNORECASE,
)
