"""Scheduling and reminder engine for Endtime tasks."""
import re
import os
import shutil
import subprocess
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, Any, Tuple, List, TYPE_CHECKING
from endtime.config import INLINE_SCHEDULE_REGEX

if TYPE_CHECKING:
    from textual.app import App


def parse_time_component(time_str: str) -> Optional[Tuple[int, int]]:
    """Parse time string like '14:30', '14.30', '2:30pm', '7pm', '8am' into (hour, minute)."""
    t_clean = time_str.strip().lower().replace(".", ":")
    is_pm = "pm" in t_clean
    is_am = "am" in t_clean
    t_clean = t_clean.replace("pm", "").replace("am", "").strip()

    parts = t_clean.split(":")
    try:
        if len(parts) == 1:
            hour = int(parts[0])
            minute = 0
        elif len(parts) == 2:
            hour = int(parts[0])
            minute = int(parts[1])
        else:
            return None

        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)
    except ValueError:
        return None
    return None


def parse_schedule_string(schedule_str: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """Parse natural schedule string into a concrete datetime object."""
    if not schedule_str:
        return None

    if now is None:
        now = datetime.now()

    s = schedule_str.strip().lower()
    if s.startswith("@"):
        s = s[1:].strip()

    # 1. Relative offsets: "in 15m", "+15m", "15m", "1h", "in 2 hours", "30s"
    rel_match = re.match(r'^(?:in\s+|\+)?(\d+)\s*(s|sec|secs|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$', s)
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit.startswith("s"):
            return now + timedelta(seconds=qty)
        elif unit.startswith("m"):
            return now + timedelta(minutes=qty)
        elif unit.startswith("h"):
            return now + timedelta(hours=qty)
        elif unit.startswith("d"):
            return now + timedelta(days=qty)

    # 2. Named tokens: "tomorrow", "tmrw", "today", "tonight"
    if s in ("tomorrow", "tmrw"):
        target_date = (now + timedelta(days=1)).date()
        return datetime.combine(target_date, time(9, 0))

    if s == "tonight":
        target_time = time(20, 0)
        target_date = now.date()
        if now.time() >= target_time:
            target_date += timedelta(days=1)
        return datetime.combine(target_date, target_time)

    # "tomorrow 14:30" or "tmrw 9am"
    tmrw_match = re.match(r'^(?:tomorrow|tmrw)\s+(.+)$', s)
    if tmrw_match:
        time_part = parse_time_component(tmrw_match.group(1))
        if time_part:
            target_date = (now + timedelta(days=1)).date()
            return datetime.combine(target_date, time(time_part[0], time_part[1]))

    # "today 18:00" or "today 6pm"
    today_match = re.match(r'^today\s+(.+)$', s)
    if today_match:
        time_part = parse_time_component(today_match.group(1))
        if time_part:
            return datetime.combine(now.date(), time(time_part[0], time_part[1]))

    # 3. Plain time of day: "14:30", "14.30", "2:30pm", "7pm"
    time_part = parse_time_component(s)
    if time_part:
        target_time = time(time_part[0], time_part[1])
        target_date = now.date()
        # If time has already passed today, schedule for tomorrow
        if now.time() >= target_time:
            target_date += timedelta(days=1)
        return datetime.combine(target_date, target_time)

    # 4. Explicit date + optional time: "2026-09-01 14:00" or "2026-09-01"
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M%p", "%Y-%m-%d", "%m-%d %H:%M", "%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if "%Y" not in fmt:
                dt = dt.replace(year=now.year)
            if "%H" not in fmt and "%I" not in fmt:
                dt = dt.replace(hour=9, minute=0)
            return dt
        except ValueError:
            pass

    return None


def format_schedule_badge(scheduled_dt: datetime, now: Optional[datetime] = None) -> str:
    """Format a scheduled datetime into a concise status string like '⏰ in 14m' or '⏰ OVERDUE'."""
    if now is None:
        now = datetime.now()

    diff = (scheduled_dt - now).total_seconds()

    if diff < -60:
        # Overdue
        abs_diff = int(abs(diff))
        if abs_diff < 3600:
            return f"[#ff4444][b]⏰ [OVERDUE] ({abs_diff // 60}m)[/b][/]"
        elif abs_diff < 86400:
            return f"[#ff4444][b]⏰ [OVERDUE] ({abs_diff // 3600}h)[/b][/]"
        else:
            return f"[#ff4444][b]⏰ [OVERDUE] ({scheduled_dt.strftime('%b %d')})[/b][/]"
    elif diff < 0:
        return "[#ff4444][b]⏰ [DUE NOW][/b][/]"
    elif diff < 60:
        return "[#ff4444][b]⏰ in <1m[/b][/]"
    elif diff < 3600:
        mins = int(diff // 60)
        return f"[#666666]⏰[/] [#888888]in {mins}m[/]"
    elif scheduled_dt.date() == now.date():
        time_str = scheduled_dt.strftime("%H:%M")
        hours = int(diff // 3600)
        return f"[#666666]⏰[/] [#888888]{time_str} (in {hours}h)[/]"
    elif scheduled_dt.date() == (now + timedelta(days=1)).date():
        time_str = scheduled_dt.strftime("%H:%M")
        return f"[#555555]⏰ tmrw {time_str}[/]"
    else:
        return f"[#555555]⏰ {scheduled_dt.strftime('%b %d %H:%M')}[/]"


def send_desktop_notification(title: str, message: str) -> None:
    """Send non-blocking desktop notification using native Linux/macOS utilities."""
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(
                ["notify-send", "-a", "Endtime", "-u", "critical", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

    if shutil.which("osascript"):
        try:
            script = f'display notification "{message}" with title "{title}" sound name "Glass"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


class ScheduleManager:
    """Manages scheduled tasks, background reminder ticking, and snooze actions."""

    def __init__(self, app: "App"):
        self.app = app
        self._ticker_interval = None
        self._last_date = date.today()

    def start_ticker(self) -> None:
        """Start the 1-second interval scheduler ticker."""
        if hasattr(self.app, "set_interval"):
            self._ticker_interval = self.app.set_interval(1.0, self.tick)

    def stop_ticker(self) -> None:
        """Stop the interval ticker."""
        if self._ticker_interval is not None:
            try:
                self._ticker_interval.stop()
            except Exception:
                pass
            self._ticker_interval = None

    def tick(self) -> None:
        """Check all tasks for triggered schedule reminders, update live badges, and handle day rollover."""
        now = datetime.now()
        today = now.date()
        tasks_data = getattr(self.app, "tasks_data", [])

        if today != self._last_date:
            self._last_date = today
            from endtime.habits import process_habits
            if process_habits(tasks_data):
                if hasattr(self.app, "schedule_save"):
                    self.app.schedule_save(tasks=True)
                if hasattr(self.app, "refresh_list"):
                    self.app.refresh_list(keep_index=True)

        save_needed = False

        for task in tasks_data:
            if task.get("completed", False):
                continue

            schedule = task.get("schedule")
            if not schedule or schedule.get("notified", False):
                continue

            remind_at_str = schedule.get("remind_at") or schedule.get("scheduled_at")
            if not remind_at_str:
                continue

            try:
                remind_at = datetime.fromisoformat(remind_at_str)
            except (ValueError, TypeError):
                continue

            if now >= remind_at:
                schedule["notified"] = True
                save_needed = True
                self._trigger_reminder(task)

        if save_needed and hasattr(self.app, "schedule_save"):
            self.app.schedule_save(tasks=True)

        self._refresh_live_badges()
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def _refresh_live_badges(self) -> None:
        """Update schedule badges in place for all visible TodoItems in the list view."""
        from textual.widgets import ListView
        from endtime.widgets.todo_item import TodoItem

        try:
            task_list = None
            try:
                task_list = self.app.query_one("#task-list", ListView)
            except Exception:
                for screen in reversed(getattr(self.app, "_screen_stack", [])):
                    try:
                        task_list = screen.query_one("#task-list", ListView)
                        break
                    except Exception:
                        continue
            if task_list is None:
                return

            for child in task_list.children:
                if isinstance(child, TodoItem):
                    task_dict = self.app.get_task_by_id(child.task_id) if hasattr(self.app, "get_task_by_id") else None
                    new_badge = self.get_schedule_badge(task_dict)
                    if child.schedule_badge != new_badge:
                        child.update_data_and_refresh(schedule_badge=new_badge)
        except Exception:
            pass

    def is_task_overdue(self, task_dict: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> bool:
        """Return True if task has an active, uncompleted schedule whose time has passed."""
        if not task_dict or task_dict.get("completed", False):
            return False
        schedule = task_dict.get("schedule")
        if not schedule:
            return False
        remind_at_str = schedule.get("remind_at") or schedule.get("scheduled_at")
        if not remind_at_str:
            return False
        if now is None:
            now = datetime.now()
        try:
            dt = datetime.fromisoformat(remind_at_str)
            return (now - dt).total_seconds() > 60
        except (ValueError, TypeError):
            return False

    def _trigger_reminder(self, task: Dict[str, Any]) -> None:
        """Trigger multi-tier reminder: audio bell, desktop notification, and in-app modal."""
        # 1. Audible terminal bell
        print("\a", end="", flush=True)

        from endtime.models import parse_task
        _, display_text = parse_task(task.get("text", ""), task)

        # 2. Desktop notification
        is_overdue = self.is_task_overdue(task)
        overdue_str = ""
        schedule = task.get("schedule") or {}
        remind_at_str = schedule.get("remind_at") or schedule.get("scheduled_at")
        if remind_at_str and is_overdue:
            try:
                dt = datetime.fromisoformat(remind_at_str)
                diff = (datetime.now() - dt).total_seconds()
                if diff < 3600:
                    overdue_str = f"{int(diff // 60)}m late"
                else:
                    overdue_str = f"{int(diff // 3600)}h late"
            except Exception:
                pass

        notif_title = "Endtime Reminder [OVERDUE]" if is_overdue else "Endtime Reminder"
        send_desktop_notification(notif_title, f"Task Due: {display_text}")

        # 3. In-app reminder modal
        from endtime.widgets.reminder_modal import ReminderModal
        try:
            # Only push modal if not already on ReminderModal
            if not isinstance(getattr(self.app, "screen", None), ReminderModal):
                self.app.push_screen(ReminderModal(task["id"], display_text, is_overdue=is_overdue, overdue_duration_str=overdue_str))
            elif hasattr(self.app, "update_prompt"):
                status_prefix = "[OVERDUE] " if is_overdue else ""
                self.app.update_prompt(f"[#ff4444][b]⏰ {status_prefix}REMINDER: {display_text}[/b][/]")
        except Exception:
            pass

    def extract_and_apply_schedule(self, task_dict: Dict[str, Any], text: str) -> str:
        """Extract inline @schedule syntax from task text, apply schedule object, and return clean text."""
        match = INLINE_SCHEDULE_REGEX.search(text)
        if match:
            raw_token = match.group(1).strip()
            dt = parse_schedule_string(raw_token)
            if dt:
                task_dict["schedule"] = {
                    "scheduled_at": dt.isoformat(),
                    "remind_at": dt.isoformat(),
                    "raw_token": f"@{raw_token}",
                    "notified": False,
                }
                # Remove @token from raw text
                clean_text = text[:match.start()].rstrip() + " " + text[match.end():].lstrip()
                clean_text = clean_text.strip()
                return clean_text
        return text

    def set_schedule(self, task_id: str, scheduled_dt: datetime) -> None:
        """Set or update the schedule for a specific task."""
        task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None
        if task_dict:
            task_dict["schedule"] = {
                "scheduled_at": scheduled_dt.isoformat(),
                "remind_at": scheduled_dt.isoformat(),
                "raw_token": scheduled_dt.strftime("%Y-%m-%d %H:%M"),
                "notified": False,
            }
            if hasattr(self.app, "schedule_save"):
                self.app.schedule_save(tasks=True)
            if hasattr(self.app, "refresh_list"):
                self.app.refresh_list(keep_index=True)

    def snooze_task(self, task_id: str, minutes: int = 10) -> None:
        """Snooze a task reminder by the specified number of minutes."""
        task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None
        if task_dict:
            new_remind = datetime.now() + timedelta(minutes=minutes)
            if "schedule" not in task_dict or not task_dict["schedule"]:
                task_dict["schedule"] = {
                    "scheduled_at": new_remind.isoformat(),
                    "remind_at": new_remind.isoformat(),
                    "notified": False,
                }
            else:
                task_dict["schedule"]["remind_at"] = new_remind.isoformat()
                task_dict["schedule"]["notified"] = False

            if hasattr(self.app, "schedule_save"):
                self.app.schedule_save(tasks=True)
            if hasattr(self.app, "refresh_list"):
                self.app.refresh_list(keep_index=True)

    def clear_schedule(self, task_id: str) -> None:
        """Remove scheduled reminder from task."""
        task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None
        if task_dict and "schedule" in task_dict:
            task_dict["schedule"] = None
            if hasattr(self.app, "schedule_save"):
                self.app.schedule_save(tasks=True)
            if hasattr(self.app, "refresh_list"):
                self.app.refresh_list(keep_index=True)

    def get_schedule_badge(self, task_dict: Optional[Dict[str, Any]]) -> str:
        """Get formatted schedule badge for task row."""
        if not task_dict or not task_dict.get("schedule"):
            return ""
        sched = task_dict["schedule"]
        dt_str = sched.get("remind_at") or sched.get("scheduled_at")
        if not dt_str:
            return ""
        try:
            dt = datetime.fromisoformat(dt_str)
            return format_schedule_badge(dt)
        except (ValueError, TypeError):
            return ""
