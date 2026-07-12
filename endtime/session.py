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


class SessionManager:
    """Manages active Pomodoro and Stopwatch working sessions attached to tasks."""

    def __init__(self, app: "App"):
        self.app = app
        self.active_task_id: Optional[str] = None
        self.session_type: str = SessionType.IDLE
        self.state: str = SessionState.IDLE
        self.duration_seconds: int = 0
        self.elapsed_seconds: int = 0
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

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        self.app.update_header()

    def cancel_session(self) -> None:
        """Stop and discard the active working session without saving elapsed time."""
        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.elapsed_seconds = 0

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
                    # Save work and transition to finished notice
                    self.stop_and_save()
                    self.app.update_prompt("[#ffffff][b]POMODORO FINISHED![/b] Press 'w' on a task to start a 5m break.[/]")
                    return
                else:
                    self.cancel_session()
                    self.app.update_prompt("[#ffffff][b]BREAK FINISHED![/b] Ready to focus again.[/]")
                    return

        self._refresh_active_widget()
        self.app.update_header()

    def get_badge_text(self) -> str:
        """Get minimalist session badge for the task row (e.g. 'P 24:59')."""
        if self.state == SessionState.IDLE:
            return ""

        if self.session_type == SessionType.STOPWATCH:
            time_str = format_duration(self.elapsed_seconds)
            prefix = "T "
        else:
            time_str = format_duration(self.duration_seconds)
            prefix = "P " if self.session_type == SessionType.POMODORO else "B "

        if self.state == SessionState.PAUSED:
            return f"{prefix}{time_str} (paused)"
        return f"{prefix}{time_str}"

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
            for screen in getattr(self.app, "screen_stack", [self.app.screen]):
                try:
                    task_list = screen.query_one("#task-list", ListView)
                    break
                except Exception:
                    continue
            if not task_list:
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
