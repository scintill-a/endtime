"""Domain models and task parsing utilities for Endtime."""
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

