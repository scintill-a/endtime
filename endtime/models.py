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
