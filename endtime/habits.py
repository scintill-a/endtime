"""Habit and daily streak processing logic for Endtime."""
from datetime import date, timedelta
from typing import List, Dict, Any
from endtime.models import parse_task


def process_habits(tasks_data: List[Dict[str, Any]]) -> bool:
    """Check daily habits, rollover streaks, and reset daily completion/timer state. Returns True if modified."""
    today_str = date.today().isoformat()
    changed = False
    
    for t in tasks_data:
        tag, _ = parse_task(t.get("text", ""), t)
        if tag == "DAILY":
            completed_dates = t.get("completed_dates", [])
            last_habit_date = t.get("last_habit_date")
            is_new_day = (last_habit_date != today_str)

            # Reset completion if not completed today
            if today_str not in completed_dates and t.get("completed", False):
                t["completed"] = False
                if "completed_at" in t:
                    del t["completed_at"]
                changed = True

            # Reset daily timer data (time spent and saved session) when day rolls over
            if is_new_day:
                if today_str not in completed_dates:
                    if t.get("time_spent_seconds", 0) > 0:
                        t["time_spent_seconds"] = 0
                        changed = True
                    if t.get("saved_session"):
                        t["saved_session"] = None
                        changed = True
                t["last_habit_date"] = today_str
                changed = True

            # Calculate streak
            streak = 0
            check_date = date.today()
            if today_str not in completed_dates:
                check_date -= timedelta(days=1)
            
            while check_date.isoformat() in completed_dates:
                streak += 1
                check_date -= timedelta(days=1)
            
            if t.get("streak") != streak:
                t["streak"] = streak
                changed = True

    return changed
