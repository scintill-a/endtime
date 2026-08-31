"""Domain models and task parsing utilities for Endtime."""
import re
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, Tuple
from endtime.config import TAG_REGEX


def parse_task(text: str, task_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """Parse category tag and display text from raw task string with O(1) dictionary caching."""
    if task_data is not None and task_data.get("_cached_text") == text:
        return task_data["_tag"], task_data["_display"]
    
    match = TAG_REGEX.match(text)
    if match:
        tag, display = match.group(1).strip().upper(), match.group(2)
    else:
        tag, display = "GENERAL", text
        
    if task_data is not None and isinstance(task_data, dict):
        task_data["_cached_text"] = text
        task_data["_tag"] = tag
        task_data["_display"] = display
        
    return tag, display


def format_duration(seconds: int) -> str:
    """Format seconds into MM:SS or HH:MM:SS for active timer display."""
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def format_accumulated_time(seconds: int) -> str:
    """Format total spent seconds into a concise string like '1h 24m' or '45m'."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"


def render_progress_bar(current: int, total: int, width: int = 16) -> str:
    """Render a sleek Unicode block progress bar."""
    if total <= 0:
        pct = 0.0
    else:
        pct = min(1.0, max(0.0, current / total))
    filled_len = int(round(width * pct))
    bar = "█" * filled_len + "░" * (width - filled_len)
    return f"[{bar}] {int(pct * 100)}%"


def render_smooth_progress_bar(current: int, total: int, width: int = 24) -> str:
    """Render a smooth horizontal track progress bar with head indicator."""
    if total <= 0:
        pct = 0.0
    else:
        pct = min(1.0, max(0.0, current / total))
    filled_len = int(round(width * pct))
    if filled_len >= width:
        bar = "━" * width
    elif filled_len > 0:
        bar = "━" * (filled_len - 1) + "╸" + "─" * (width - filled_len)
    else:
        bar = "─" * width
    return f"{bar} {int(pct * 100)}%"


def parse_timer_input(raw: str) -> Optional[Tuple[int, str]]:
    """
    Parse natural duration or target clock time from user string.
    
    Supported formats:
    - '15m', '45m', '10 min', '1h', '1h30m', '90m', '45s'
    - '25:00', '1:30:00'
    - '20' (defaults to 20 minutes)
    - 'until 17:30', 'until 5:00pm', '17:30', '5:00pm'
    
    Returns (duration_seconds, label) or None if invalid.
    """
    s = raw.strip().lower()
    if not s:
        return None

    # Target clock time with 'until' or 'at' prefix (e.g. 'until 17:30', 'at 5pm')
    until_match = re.match(r'^(?:until|at|by)\s+(.+)$', s)
    if until_match:
        target_str = until_match.group(1).strip()
        return _parse_clock_target(target_str)

    # Check HH:MM target time pattern (e.g., '17:30' or '5:30pm')
    clock_res = _parse_clock_target(s)
    if clock_res is not None:
        return clock_res

    # Check MM:SS or HH:MM:SS colon notation (e.g. '25:00', '1:30:00')
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            mins, secs = int(parts[0]), int(parts[1])
            total = mins * 60 + secs
            if total > 0:
                return total, f"{mins}:{secs:02d}"
        elif len(parts) == 3 and all(p.isdigit() for p in parts):
            hrs, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
            total = hrs * 3600 + mins * 60 + secs
            if total > 0:
                return total, f"{hrs}:{mins:02d}:{secs:02d}"

    # Check composite duration like '1h30m', '1h 30m', '45m', '30s'
    pattern = re.compile(r'(?:(\d+)\s*h(?:ours?|rs?)?)?\s*(?:(\d+)\s*m(?:in(?:ute)?s?)?)?\s*(?:(\d+)\s*s(?:ec(?:ond)?s?)?)?$')
    m = pattern.match(s)
    if m and any(m.groups()):
        hrs = int(m.group(1)) if m.group(1) else 0
        mins = int(m.group(2)) if m.group(2) else 0
        secs = int(m.group(3)) if m.group(3) else 0
        total = hrs * 3600 + mins * 60 + secs
        if total > 0:
            label_parts = []
            if hrs: label_parts.append(f"{hrs}h")
            if mins: label_parts.append(f"{mins}m")
            if secs: label_parts.append(f"{secs}s")
            return total, " ".join(label_parts)

    # Pure number defaults to minutes
    if s.isdigit():
        val = int(s)
        if val > 0:
            return val * 60, f"{val}m"

    return None


def _parse_clock_target(time_str: str) -> Optional[Tuple[int, str]]:
    """Parse time target like '17:30', '5:30pm', '5pm' and calculate delta from now."""
    time_str = time_str.strip().upper()
    formats = [
        "%H:%M",
        "%H:%M:%S",
        "%I:%M%p",
        "%I:%M %p",
        "%I%p",
        "%I %p",
    ]
    parsed_time = None
    for fmt in formats:
        try:
            parsed_time = datetime.strptime(time_str, fmt).time()
            break
        except ValueError:
            continue

    if not parsed_time:
        return None

    now = datetime.now()
    target_dt = datetime.combine(now.date(), parsed_time)
    
    # If target time is already in the past today, assume tomorrow
    if target_dt <= now:
        target_dt += timedelta(days=1)

    delta_secs = int((target_dt - now).total_seconds())
    if delta_secs <= 0:
        return None

    display_target = target_dt.strftime("%H:%M")
    return delta_secs, f"Until {display_target}"
