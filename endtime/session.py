"""Working session (Pomodoro, Stopwatch, and Scheduled Timers) manager for Endtime."""
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from endtime.models import format_duration, parse_task

if TYPE_CHECKING:
    from textual.app import App


class SessionType:
    IDLE = "IDLE"
    POMODORO = "POMODORO"
    BREAK = "BREAK"
    STOPWATCH = "STOPWATCH"
    SCHEDULED = "SCHEDULED"
    CUSTOM = "CUSTOM"


class SessionState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_BREAK = "WAITING_BREAK"
    WAITING_WORK = "WAITING_WORK"
    ALARM = "ALARM"


class SessionManager:
    """Manages active Pomodoro, Stopwatch, and Scheduled Timer sessions attached to tasks."""

    def __init__(self, app: "App"):
        self.app = app
        self.active_task_id: Optional[str] = None
        self.session_type: str = SessionType.IDLE
        self.state: str = SessionState.IDLE
        self.duration_seconds: int = 0      # Remaining seconds for countdown timers
        self.total_duration: int = 0        # Initial total duration for progress calculation
        self.elapsed_seconds: int = 0       # Elapsed seconds in current active segment
        self.pomodoro_round: int = 1
        self.is_break: bool = False
        self.session_label: str = ""
        self._interval_timer = None

    def start_session(
        self,
        task_id: str,
        session_type: str,
        duration: int = 0,
        total_duration: Optional[int] = None,
        pomodoro_round: int = 1,
        is_break: bool = False,
        label: str = "",
    ) -> None:
        """Start a new working session for the given task."""
        # If another session is running, save and pause it
        if self.state != SessionState.IDLE and self.active_task_id and self.active_task_id != task_id:
            self.save_and_pause()

        self.active_task_id = task_id
        self.session_type = session_type
        self.state = SessionState.RUNNING
        self.duration_seconds = duration
        self.total_duration = total_duration if total_duration is not None else duration
        self.elapsed_seconds = 0
        self.pomodoro_round = pomodoro_round
        self.is_break = is_break
        self.session_label = label

        self._persist_session_state()
        self._start_interval()
        self._refresh_active_widget()
        self.app.update_header()

    def continue_session(self, task_id: str) -> bool:
        """Resume a saved or paused session from task metadata."""
        task_dict = self.app.get_task_by_id(task_id)
        if not task_dict:
            return False

        session_data = task_dict.get("session_data")
        if not session_data:
            # Fallback: start stopwatch if no saved session data exists
            self.start_session(task_id, SessionType.STOPWATCH, duration=0)
            return True

        if self.state != SessionState.IDLE and self.active_task_id and self.active_task_id != task_id:
            self.save_and_pause()

        self.active_task_id = task_id
        self.session_type = session_data.get("type", SessionType.POMODORO)
        self.duration_seconds = session_data.get("duration_seconds", 25 * 60)
        self.total_duration = session_data.get("total_duration", self.duration_seconds)
        self.elapsed_seconds = 0
        self.pomodoro_round = session_data.get("pomodoro_round", 1)
        self.is_break = session_data.get("is_break", False)
        self.session_label = session_data.get("label", "")
        self.state = SessionState.RUNNING

        self._persist_session_state()
        self._start_interval()
        self._refresh_active_widget()
        self.app.update_header()
        return True

    def toggle_pause(self) -> None:
        """Pause or resume the active working session."""
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED
            self._commit_elapsed_time()
            self._stop_interval()
        elif self.state == SessionState.PAUSED:
            self.state = SessionState.RUNNING
            self._start_interval()
        elif self.state == SessionState.ALARM:
            self.state = SessionState.PAUSED
            self._stop_interval()

        self._persist_session_state()
        self._refresh_active_widget()
        self._refresh_overlay_modal()
        self.app.update_header()

    def save_and_pause(self) -> None:
        """Pause active session, commit elapsed time to task, persist state to disk, and keep ready for resume."""
        self._commit_elapsed_time()
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED
        self._stop_interval()
        self._persist_session_state()
        self.app.schedule_save(tasks=True)

        if self.active_task_id:
            self._refresh_widget_by_id(self.active_task_id)
        self._refresh_overlay_modal()
        self.app.update_header()

    def add_time(self, seconds: int = 300) -> None:
        """Add additional time (e.g. +5m) to the active session."""
        self.duration_seconds += seconds
        self.total_duration += seconds
        if self.state == SessionState.ALARM:
            self.state = SessionState.RUNNING
            self._start_interval()
        self._persist_session_state()
        self._refresh_active_widget()
        self._refresh_overlay_modal()
        self.app.update_header()

    def transition_next(self) -> None:
        """User-mediated transition to the next phase (Break or next Pomodoro Cycle)."""
        if self.state == SessionState.WAITING_BREAK:
            self.is_break = True
            self.duration_seconds = 5 * 60
            self.total_duration = 5 * 60
            self.state = SessionState.RUNNING
            self.elapsed_seconds = 0
            self._persist_session_state()
            self._start_interval()
            self._refresh_active_widget()
            self._refresh_overlay_modal()
            self.app.update_header()
        elif self.state == SessionState.WAITING_WORK:
            self.is_break = False
            self.pomodoro_round += 1
            self.duration_seconds = 25 * 60
            self.total_duration = 25 * 60
            self.state = SessionState.RUNNING
            self.elapsed_seconds = 0
            self._persist_session_state()
            self._start_interval()
            self._refresh_active_widget()
            self._refresh_overlay_modal()
            self.app.update_header()

    def stop_and_save(self) -> None:
        """Save progress, mark session complete/idle, and persist accumulated time."""
        self._commit_elapsed_time()
        self._clear_task_session_data()

        old_task_id = self.active_task_id
        self._stop_interval()
        self._reset_state()

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.schedule_save(tasks=True)
        self.app.update_header()

    def tick_and_save(self) -> None:
        """Mark active task completed, save accumulated duration, clear session, and stop."""
        self._commit_elapsed_time()
        self._clear_task_session_data()

        if self.active_task_id:
            task = self.app.get_task_by_id(self.active_task_id)
            if task:
                from datetime import date
                task["completed"] = not task.get("completed", False)
                if task["completed"]:
                    task["completed_at"] = datetime.now().isoformat()
                else:
                    if "completed_at" in task:
                        del task["completed_at"]
                        
                tag, _ = parse_task(task["text"], task)
                if tag == "DAILY":
                    today_str = date.today().isoformat()
                    completed_dates = task.get("completed_dates", [])
                    if task["completed"] and today_str not in completed_dates:
                        completed_dates.append(today_str)
                    elif not task["completed"] and today_str in completed_dates:
                        completed_dates.remove(today_str)
                    task["completed_dates"] = completed_dates
                    
                self.app.schedule_save(tasks=True)
                self.app.refresh_list(keep_index=True)

        old_task_id = self.active_task_id
        self._stop_interval()
        self._reset_state()

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.update_header()

    def cancel_session(self) -> None:
        """Cancel current session and clear saved session metadata."""
        self._clear_task_session_data()
        old_task_id = self.active_task_id
        self._stop_interval()
        self._reset_state()

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.schedule_save(tasks=True)
        self.app.update_header()

    def reset_task_session(self, task_id: str) -> None:
        """Reset all session data and time spent on a specific task."""
        if self.active_task_id == task_id:
            self._stop_interval()
            self._reset_state()
            
        task = self.app.get_task_by_id(task_id)
        if task:
            task["time_spent_seconds"] = 0
            if "session_data" in task:
                del task["session_data"]
            self.app.schedule_save(tasks=True)
            self._refresh_widget_by_id(task_id)
            self.app.update_header()

    def _commit_elapsed_time(self) -> None:
        """Add in-memory elapsed seconds to task's total accumulated time."""
        if self.active_task_id and self.elapsed_seconds > 0:
            for t in getattr(self.app, "tasks_data", []):
                if t["id"] == self.active_task_id:
                    t["time_spent_seconds"] = t.get("time_spent_seconds", 0) + self.elapsed_seconds
                    break
            self.elapsed_seconds = 0
            self.app.schedule_save(tasks=True)

    def _persist_session_state(self) -> None:
        """Persist current session parameters into the active task's JSON object."""
        if not self.active_task_id:
            return
        task = self.app.get_task_by_id(self.active_task_id)
        if not task:
            return

        task["session_data"] = {
            "type": self.session_type,
            "state": self.state,
            "duration_seconds": self.duration_seconds,
            "total_duration": self.total_duration,
            "pomodoro_round": self.pomodoro_round,
            "is_break": self.is_break,
            "label": self.session_label,
            "updated_at": datetime.now().isoformat(),
        }
        self.app.schedule_save(tasks=True)

    def _clear_task_session_data(self) -> None:
        """Remove session_data from the active task dictionary."""
        if self.active_task_id:
            task = self.app.get_task_by_id(self.active_task_id)
            if task and "session_data" in task:
                del task["session_data"]
                self.app.schedule_save(tasks=True)

    def _reset_state(self) -> None:
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.total_duration = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False
        self.session_label = ""

    def _start_interval(self) -> None:
        self._stop_interval()
        self._interval_timer = self.app.set_interval(1.0, self._on_tick)

    def _stop_interval(self) -> None:
        if self._interval_timer is not None:
            try:
                self._interval_timer.stop()
            except Exception:
                pass
            self._interval_timer = None

    def _on_tick(self) -> None:
        if self.state != SessionState.RUNNING:
            return

        self.elapsed_seconds += 1

        if self.session_type in (SessionType.POMODORO, SessionType.BREAK, SessionType.SCHEDULED, SessionType.CUSTOM):
            self.duration_seconds -= 1
            if self.duration_seconds <= 0:
                self.duration_seconds = 0
                print("\a", end="", flush=True)  # Audible terminal bell
                self._commit_elapsed_time()

                if self.session_type == SessionType.POMODORO:
                    if not self.is_break:
                        self.state = SessionState.WAITING_BREAK
                        self._persist_session_state()
                        self._stop_interval()
                    else:
                        self.state = SessionState.WAITING_WORK
                        self._persist_session_state()
                        self._stop_interval()
                else:
                    # Scheduled or Custom timer finished -> ALARM state
                    self.state = SessionState.ALARM
                    self._persist_session_state()
                    self._stop_interval()

                self._refresh_active_widget()
                self._refresh_overlay_modal()
                self.app.update_header()
                return

        # Periodic background state save every 10 seconds
        if self.elapsed_seconds % 10 == 0:
            self._persist_session_state()

        self._refresh_active_widget()
        self._refresh_overlay_modal()
        self.app.update_header()

    def get_active_progress(self) -> Tuple[int, int, float]:
        """Return (elapsed_seconds, total_duration, progress_ratio 0.0-1.0)."""
        if self.session_type == SessionType.STOPWATCH:
            total_spent = self.elapsed_seconds
            if self.active_task_id:
                task = self.app.get_task_by_id(self.active_task_id)
                if task:
                    total_spent += task.get("time_spent_seconds", 0)
            return self.elapsed_seconds, max(1, total_spent), 1.0

        total = max(1, self.total_duration)
        remaining = max(0, self.duration_seconds)
        elapsed = max(0, total - remaining)
        ratio = min(1.0, max(0.0, elapsed / total))
        return elapsed, total, ratio

    def get_badge_text(self) -> str:
        """Get minimalist session badge for task row (e.g. '⏵ 24:59' or '⏸ 14:02')."""
        if self.state == SessionState.IDLE:
            return ""

        if self.session_type == SessionType.STOPWATCH:
            time_str = format_duration(self.elapsed_seconds)
            prefix = "⏱ "
        elif self.session_type == SessionType.SCHEDULED:
            time_str = format_duration(self.duration_seconds)
            prefix = "⏰ "
        else:
            time_str = format_duration(self.duration_seconds)
            prefix = "☕ " if self.is_break else "🍅 "

        if self.state in (SessionState.PAUSED, SessionState.WAITING_BREAK, SessionState.WAITING_WORK):
            return f"⏸ {prefix}{time_str}"
        elif self.state == SessionState.ALARM:
            return f"🔔 {prefix}00:00 (DONE)"
        return f"⏵ {prefix}{time_str}"

    def get_saved_task_badge(self, task_dict: Dict[str, Any]) -> str:
        """Get badge for a task with saved/paused session state that isn't currently active."""
        if not task_dict or "session_data" not in task_dict:
            return ""
        s = task_dict["session_data"]
        stype = s.get("type", SessionType.POMODORO)
        rem = s.get("duration_seconds", 0)
        time_str = format_duration(rem)
        if stype == SessionType.STOPWATCH:
            return "⏸ ⏱ saved"
        elif stype == SessionType.SCHEDULED:
            return f"⏸ ⏰ {time_str}"
        else:
            return f"⏸ 🍅 {time_str}"

    def get_overlay_title(self) -> str:
        """Get stylized overlay header title string."""
        if self.session_type == SessionType.STOPWATCH:
            return "S T O P W A T C H"
        if self.session_type == SessionType.POMODORO:
            if self.is_break:
                return f"S H O R T   B R E A K   —   C Y C L E   {self.pomodoro_round}"
            return f"P O M O D O R O   —   C Y C L E   {self.pomodoro_round}"
        if self.session_type == SessionType.SCHEDULED:
            label = f"  ({self.session_label})" if self.session_label else ""
            return f"S C H E D U L E D   T I M E R{label}"
        if self.session_type == SessionType.CUSTOM:
            label = f"  ({self.session_label})" if self.session_label else ""
            return f"C U S T O M   T I M E R{label}"
        return "S E S S I O N"

    def get_header_badge(self) -> str:
        """Get header bar badge string for the currently active session."""
        if self.state == SessionState.IDLE or not self.active_task_id:
            return ""

        task_display = "Task"
        for t in getattr(self.app, "tasks_data", []):
            if t["id"] == self.active_task_id:
                _, task_display = parse_task(t["text"], t)
                break

        display_name = task_display[:22] + "…" if len(task_display) > 22 else task_display
        status_sym = "⚡" if self.state == SessionState.RUNNING else ("⏸" if self.state == SessionState.PAUSED else "🔔")
        color = "#00e676" if self.state == SessionState.RUNNING else ("#ffa502" if self.state == SessionState.PAUSED else "#ff3355")
        badge = self.get_badge_text()
        return f"[{color}]{status_sym} {badge}[/] [#94a3b8]•[/] [#ffffff]{display_name}[/]"

    def _refresh_active_widget(self) -> None:
        if self.active_task_id:
            self._refresh_widget_by_id(self.active_task_id)

    def _refresh_overlay_modal(self) -> None:
        from endtime.widgets.session_overlay import SessionOverlayModal
        try:
            if isinstance(getattr(self.app, "screen", None), SessionOverlayModal):
                self.app.screen._on_tick()
        except Exception:
            pass

    def _refresh_widget_by_id(self, task_id: str) -> None:
        from textual.widgets import ListView
        from endtime.widgets.todo_item import TodoItem
        try:
            task_list = None
            for screen in getattr(self.app, "screen_stack", []) + [getattr(self.app, "screen", None)]:
                if screen is None:
                    continue
                try:
                    task_list = screen.query_one("#task-list", ListView)
                    break
                except Exception:
                    continue
            if task_list is None:
                try:
                    task_list = self.app.query_one("#task-list", ListView)
                except Exception:
                    return
            if task_list is None:
                return

            for child in task_list.children:
                if isinstance(child, TodoItem) and child.task_id == task_id:
                    task_dict = self.app.get_task_by_id(task_id)
                    time_spent = task_dict.get("time_spent_seconds", 0) if task_dict else 0
                    if self.active_task_id == task_id:
                        badge = self.get_badge_text()
                    elif task_dict and "session_data" in task_dict:
                        badge = self.get_saved_task_badge(task_dict)
                    else:
                        badge = ""
                    child.update_data_and_refresh(
                        session_badge=badge,
                        time_spent_seconds=time_spent,
                    )
                    break
        except Exception:
            pass
