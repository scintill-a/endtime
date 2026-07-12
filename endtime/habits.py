"""Habit and daily streak processing logic for Endtime."""
from datetime import date, timedelta
from typing import List, Dict, Any
from endtime.models import parse_task


def process_habits(tasks_data: List[Dict[str, Any]]) -> bool:
    """Check daily habits and rollover streaks. Returns True if any task completion state changed."""
    today_str = date.today().isoformat()
    changed = False
    
    for t in tasks_data:
        tag, _ = parse_task(t.get("text", ""), t)
        if tag == "DAILY":
            completed_dates = t.get("completed_dates", [])
            
            # Reset completion if not completed today
            if today_str not in completed_dates and t.get("completed", False):
                t["completed"] = False
                if "completed_at" in t:
                    del t["completed_at"]
                changed = True

            # Calculate streak
            streak = 0
            check_date = date.today()
            if today_str not in completed_dates:
                check_date -= timedelta(days=1)
            
            while check_date.isoformat() in completed_dates:
                streak += 1
                check_date -= timedelta(days=1)
            
            t["streak"] = streak

    return changed
