"""Working session (Pomodoro and Stopwatch timer) manager for Endtime."""
from typing import Optional, TYPE_CHECKING
from endtime.models import format_duration, parse_task

if TYPE_CHECKING:
    from textual.app import App
    from endtime.widgets.todo_item import TodoItem


class SessionType:
    IDLE = "IDLE"
    POMODORO = "POMODORO"
    BREAK = "BREAK"
    STOPWATCH = "STOPWATCH"


class SessionState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_BREAK = "WAITING_BREAK"
    WAITING_WORK = "WAITING_WORK"


class SessionManager:
    """Manages active Pomodoro and Stopwatch working sessions attached to tasks."""

    def __init__(self, app: "App"):
        self.app = app
        self.active_task_id: Optional[str] = None
        self.session_type: str = SessionType.IDLE
        self.state: str = SessionState.IDLE
        self.duration_seconds: int = 0
        self.elapsed_seconds: int = 0
        self.pomodoro_round: int = 1
        self.is_break: bool = False
        self._interval_timer = None

    def start_session(self, task_id: str, session_type: str, duration: int = 0) -> None:
        """Start a new working session for the given task."""
        # Save previous session if one was active
        if self.state != SessionState.IDLE and self.active_task_id:
            self.stop_and_save()

        self.active_task_id = task_id
        self.session_type = session_type
        self.state = SessionState.RUNNING
        self.duration_seconds = duration
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        self._start_interval()
        self._refresh_active_widget()
        self.app.update_header()

    def toggle_pause(self) -> None:
        """Pause or resume the active working session."""
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED
            self._stop_interval()
        elif self.state == SessionState.PAUSED:
            self.state = SessionState.RUNNING
            self._start_interval()
        self._refresh_active_widget()
        self.app.update_header()

    def transition_next(self) -> None:
        """User-mediated transition to the next phase (Break or next Pomodoro Cycle)."""
        if self.state == SessionState.WAITING_BREAK:
            self.is_break = True
            self.duration_seconds = 5 * 60
            self.state = SessionState.RUNNING
            self._start_interval()
            self._refresh_active_widget()
            self._refresh_overlay_modal()
            self.app.update_header()
        elif self.state == SessionState.WAITING_WORK:
            self.is_break = False
            self.pomodoro_round += 1
            self.duration_seconds = 25 * 60
            self.state = SessionState.RUNNING
            self._start_interval()
            self._refresh_active_widget()
            self._refresh_overlay_modal()
            self.app.update_header()

    def stop_and_save(self) -> None:
        """Stop the active session and persist accumulated time spent on the task."""
        if self.active_task_id and self.elapsed_seconds > 0:
            for t in getattr(self.app, "tasks_data", []):
                if t["id"] == self.active_task_id:
                    t["time_spent_seconds"] = t.get("time_spent_seconds", 0) + self.elapsed_seconds
                    self.app.schedule_save(tasks=True)
                    break

        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.update_header()

    def tick_and_save(self) -> None:
        """Mark the active task completed (tick checkbox), save accumulated duration, and stop session."""
        if self.active_task_id:
            for t in getattr(self.app, "tasks_data", []):
                if t["id"] == self.active_task_id:
                    from datetime import datetime, date
                    if self.elapsed_seconds > 0:
                        t["time_spent_seconds"] = t.get("time_spent_seconds", 0) + self.elapsed_seconds
                    
                    t["completed"] = not t.get("completed", False)
                    if t["completed"]:
                        t["completed_at"] = datetime.now().isoformat()
                    else:
                        if "completed_at" in t:
                            del t["completed_at"]
                            
                    tag, _ = parse_task(t["text"], t)
                    if tag == "DAILY":
                        today_str = date.today().isoformat()
                        completed_dates = t.get("completed_dates", [])
                        if t["completed"] and today_str not in completed_dates:
                            completed_dates.append(today_str)
                        elif not t["completed"] and today_str in completed_dates:
                            if today_str in completed_dates:
                                completed_dates.remove(today_str)
                        t["completed_dates"] = completed_dates
                        
                    self.app.schedule_save(tasks=True)
                    self.app.refresh_list(keep_index=True)
                    break

        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.update_header()

    def cancel_session(self) -> None:
        """Cancel and discard the current session without saving elapsed time."""
        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.update_header()

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

        if self.session_type in (SessionType.POMODORO, SessionType.BREAK):
            self.duration_seconds -= 1
            if self.duration_seconds <= 0:
                print("\a", end="", flush=True)  # Ring terminal bell
                if self.session_type == SessionType.POMODORO:
                    if not self.is_break:
                        if self.active_task_id and self.elapsed_seconds > 0:
                            for t in getattr(self.app, "tasks_data", []):
                                if t["id"] == self.active_task_id:
                                    t["time_spent_seconds"] = t.get("time_spent_seconds", 0) + self.elapsed_seconds
                                    self.app.schedule_save(tasks=True)
                                    break
                        self.elapsed_seconds = 0
                        self.state = SessionState.WAITING_BREAK
                        self._stop_interval()
                        self._refresh_active_widget()
                        self._refresh_overlay_modal()
                        self.app.update_header()
                        return
                    else:
                        self.state = SessionState.WAITING_WORK
                        self._stop_interval()
                        self._refresh_active_widget()
                        self._refresh_overlay_modal()
                        self.app.update_header()
                        return

        self._refresh_active_widget()
        self._refresh_overlay_modal()
        self.app.update_header()

    def _refresh_overlay_modal(self) -> None:
        from endtime.widgets.session_overlay import SessionOverlayModal
        try:
            if isinstance(getattr(self.app, "screen", None), SessionOverlayModal):
                self.app.screen._on_tick()
        except Exception:
            pass

    def get_badge_text(self) -> str:
        """Get minimalist session badge for the task row (e.g. 'P 24:59')."""
        if self.state == SessionState.IDLE:
            return ""

        if self.session_type == SessionType.STOPWATCH:
            time_str = format_duration(self.elapsed_seconds)
            prefix = "T "
        else:
            time_str = format_duration(self.duration_seconds)
            prefix = "B " if self.is_break else "P "

        if self.state in (SessionState.PAUSED, SessionState.WAITING_BREAK, SessionState.WAITING_WORK):
            return f"{prefix}{time_str} (paused)"
        return f"{prefix}{time_str}"

    def get_overlay_title(self) -> str:
        """Get stylized overlay header title string."""
        if self.session_type == SessionType.STOPWATCH:
            return "S T O P W A T C H"
        if self.session_type == SessionType.POMODORO:
            if self.is_break:
                return f"S H O R T   B R E A K   —   C Y C L E   {self.pomodoro_round}"
            return f"P O M O D O R O   —   C Y C L E   {self.pomodoro_round}"
        return "S E S S I O N"

    def get_header_badge(self) -> str:
        """Get header bar badge string for the currently active session."""
        if self.state == SessionState.IDLE or not self.active_task_id:
            return ""

        task_display = "Unknown"
        for t in getattr(self.app, "tasks_data", []):
            if t["id"] == self.active_task_id:
                _, task_display = parse_task(t["text"], t)
                break

        return f"[{self.get_badge_text()} - {task_display}] | "

    def _refresh_active_widget(self) -> None:
        if self.active_task_id:
            self._refresh_widget_by_id(self.active_task_id)

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
                    badge = self.get_badge_text() if self.active_task_id == task_id else ""
                    child.update_data_and_refresh(
                        session_badge=badge,
                        time_spent_seconds=time_spent,
                    )
                    break
        except Exception:
            pass
