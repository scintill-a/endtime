"""Working session (Pomodoro, Break, and Stopwatch timer) manager for Endtime."""
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from datetime import datetime
from endtime.models import format_duration, parse_task

if TYPE_CHECKING:
    from textual.app import App


class SessionType:
    IDLE = "IDLE"
    POMODORO = "POMODORO"
    BREAK = "BREAK"
    LONG_BREAK = "LONG_BREAK"
    STOPWATCH = "STOPWATCH"


class SessionState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_BREAK = "WAITING_BREAK"
    WAITING_WORK = "WAITING_WORK"


class SessionManager:
    """Manages active Pomodoro, Break, and Stopwatch working sessions with snapshot continuation."""

    def __init__(self, app: "App"):
        self.app = app
        self.active_task_id: Optional[str] = None
        self.session_type: str = SessionType.IDLE
        self.state: str = SessionState.IDLE
        self.duration_seconds: int = 0
        self.total_cycle_seconds: int = 0
        self.elapsed_seconds: int = 0
        self.pomodoro_round: int = 1
        self.is_break: bool = False
        self._interval_timer = None

    def start_session(
        self,
        task_id: str,
        session_type: str,
        duration: int = 0,
        resume: bool = False,
    ) -> None:
        """Start a new working session or resume a saved snapshot for the given task."""
        # If another task has an active session, stop and preserve it
        if self.state != SessionState.IDLE and self.active_task_id and self.active_task_id != task_id:
            self.stop_and_save(preserve_snapshot=True)

        task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None

        if resume and task_dict and "saved_session" in task_dict and task_dict["saved_session"]:
            saved = task_dict["saved_session"]
            self.active_task_id = task_id
            self.session_type = saved.get("type", session_type)
            self.duration_seconds = saved.get("remaining_seconds", duration)
            self.total_cycle_seconds = saved.get("total_cycle_seconds", duration or 25 * 60)
            self.elapsed_seconds = saved.get("elapsed_seconds", 0)
            self.pomodoro_round = saved.get("pomodoro_round", 1)
            self.is_break = saved.get("is_break", False)
            self.state = SessionState.RUNNING
        else:
            self.active_task_id = task_id
            self.session_type = session_type
            self.state = SessionState.RUNNING
            self.duration_seconds = duration
            self.total_cycle_seconds = duration
            self.elapsed_seconds = 0
            self.pomodoro_round = 1
            self.is_break = (session_type in (SessionType.BREAK, SessionType.LONG_BREAK))

        # Clear saved_session while active so it's fresh, but persist state when modified
        if task_dict and "saved_session" in task_dict:
            task_dict["saved_session"] = None
            if hasattr(self.app, "schedule_save"):
                self.app.schedule_save(tasks=True)

        self._start_interval()
        self._refresh_active_widget()
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def toggle_pause(self) -> None:
        """Pause or resume the active working session, updating persisted snapshot."""
        if self.state == SessionState.RUNNING:
            self.state = SessionState.PAUSED
            self._stop_interval()
            self._persist_snapshot_to_task(self.active_task_id)
        elif self.state == SessionState.PAUSED:
            self.state = SessionState.RUNNING
            self._start_interval()
            self._persist_snapshot_to_task(self.active_task_id)
        self._refresh_active_widget()
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def transition_next(self) -> None:
        """User-mediated transition to the next phase (Break or next Pomodoro Cycle)."""
        if self.state == SessionState.WAITING_BREAK:
            self.is_break = True
            # Long break on every 4th cycle
            if self.pomodoro_round % 4 == 0:
                self.session_type = SessionType.LONG_BREAK
                self.duration_seconds = 15 * 60
                self.total_cycle_seconds = 15 * 60
            else:
                self.session_type = SessionType.BREAK
                self.duration_seconds = 5 * 60
                self.total_cycle_seconds = 5 * 60
            self.elapsed_seconds = 0
            self.state = SessionState.RUNNING
            self._start_interval()
            self._refresh_active_widget()
            self._refresh_overlay_modal()
            if hasattr(self.app, "update_header"):
                self.app.update_header()
        elif self.state == SessionState.WAITING_WORK:
            self.is_break = False
            self.session_type = SessionType.POMODORO
            self.pomodoro_round += 1
            self.duration_seconds = 25 * 60
            self.total_cycle_seconds = 25 * 60
            self.elapsed_seconds = 0
            self.state = SessionState.RUNNING
            self._start_interval()
            self._refresh_active_widget()
            self._refresh_overlay_modal()
            if hasattr(self.app, "update_header"):
                self.app.update_header()

    def stop_and_save(self, preserve_snapshot: bool = True) -> None:
        """Stop the active session, persist accumulated time, and optionally save a continuation snapshot."""
        if self.active_task_id:
            task_dict = self.app.get_task_by_id(self.active_task_id) if hasattr(self.app, "get_task_by_id") else None
            if task_dict:
                if self.elapsed_seconds > 0:
                    task_dict["time_spent_seconds"] = task_dict.get("time_spent_seconds", 0) + self.elapsed_seconds

                if preserve_snapshot and (self.duration_seconds > 0 or self.session_type == SessionType.STOPWATCH):
                    task_dict["saved_session"] = {
                        "type": self.session_type,
                        "remaining_seconds": self.duration_seconds,
                        "total_cycle_seconds": self.total_cycle_seconds,
                        "elapsed_seconds": self.elapsed_seconds if self.session_type == SessionType.STOPWATCH else 0,
                        "pomodoro_round": self.pomodoro_round,
                        "is_break": self.is_break,
                        "last_paused_at": datetime.now().isoformat(),
                    }
                else:
                    task_dict["saved_session"] = None

                if hasattr(self.app, "schedule_save"):
                    self.app.schedule_save(tasks=True)

        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.total_cycle_seconds = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def tick_and_save(self) -> None:
        """Mark the active task completed, save accumulated duration, clear session snapshot, and stop."""
        if self.active_task_id:
            task_dict = self.app.get_task_by_id(self.active_task_id) if hasattr(self.app, "get_task_by_id") else None
            if task_dict:
                from datetime import date
                if self.elapsed_seconds > 0:
                    task_dict["time_spent_seconds"] = task_dict.get("time_spent_seconds", 0) + self.elapsed_seconds

                task_dict["saved_session"] = None
                task_dict["completed"] = not task_dict.get("completed", False)
                if task_dict["completed"]:
                    task_dict["completed_at"] = datetime.now().isoformat()
                else:
                    if "completed_at" in task_dict:
                        del task_dict["completed_at"]

                tag, _ = parse_task(task_dict["text"], task_dict)
                if tag == "DAILY":
                    today_str = date.today().isoformat()
                    completed_dates = task_dict.get("completed_dates", [])
                    if task_dict["completed"] and today_str not in completed_dates:
                        completed_dates.append(today_str)
                    elif not task_dict["completed"] and today_str in completed_dates:
                        completed_dates.remove(today_str)
                    task_dict["completed_dates"] = completed_dates

                if hasattr(self.app, "schedule_save"):
                    self.app.schedule_save(tasks=True)
                if hasattr(self.app, "refresh_list"):
                    self.app.refresh_list(keep_index=True)

        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.total_cycle_seconds = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def cancel_session(self) -> None:
        """Cancel and discard active session and its snapshot."""
        if self.active_task_id:
            task_dict = self.app.get_task_by_id(self.active_task_id) if hasattr(self.app, "get_task_by_id") else None
            if task_dict:
                task_dict["saved_session"] = None
                if hasattr(self.app, "schedule_save"):
                    self.app.schedule_save(tasks=True)

        old_task_id = self.active_task_id
        self._stop_interval()
        self.state = SessionState.IDLE
        self.session_type = SessionType.IDLE
        self.active_task_id = None
        self.duration_seconds = 0
        self.total_cycle_seconds = 0
        self.elapsed_seconds = 0
        self.pomodoro_round = 1
        self.is_break = False

        if old_task_id:
            self._refresh_widget_by_id(old_task_id)
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def clear_saved_session(self, task_id: str) -> None:
        """Discard the saved session snapshot for a specific task."""
        task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None
        if task_dict and "saved_session" in task_dict:
            task_dict["saved_session"] = None
            if hasattr(self.app, "schedule_save"):
                self.app.schedule_save(tasks=True)
            self._refresh_widget_by_id(task_id)

    def reset_active_session(self) -> None:
        """Reset elapsed time and cycle duration of the currently active session."""
        if self.state == SessionState.IDLE:
            return
        if self.session_type == SessionType.STOPWATCH:
            self.elapsed_seconds = 0
        else:
            self.duration_seconds = self.total_cycle_seconds
            self.elapsed_seconds = 0
        if self.active_task_id:
            self._persist_snapshot_to_task(self.active_task_id)
        self._refresh_active_widget()
        self._refresh_overlay_modal()
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def _persist_snapshot_to_task(self, task_id: Optional[str]) -> None:
        """Write current session state snapshot to the task object."""
        if not task_id:
            return
        task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None
        if task_dict:
            task_dict["saved_session"] = {
                "type": self.session_type,
                "remaining_seconds": self.duration_seconds,
                "total_cycle_seconds": self.total_cycle_seconds,
                "elapsed_seconds": self.elapsed_seconds if self.session_type == SessionType.STOPWATCH else 0,
                "pomodoro_round": self.pomodoro_round,
                "is_break": self.is_break,
                "last_paused_at": datetime.now().isoformat(),
            }
            if hasattr(self.app, "schedule_save"):
                self.app.schedule_save(tasks=True)

    def _start_interval(self) -> None:
        self._stop_interval()
        if hasattr(self.app, "set_interval"):
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

        if self.session_type in (SessionType.POMODORO, SessionType.BREAK, SessionType.LONG_BREAK):
            self.duration_seconds -= 1
            if self.duration_seconds <= 0:
                print("\a", end="", flush=True)  # Ring terminal audio bell
                if self.session_type == SessionType.POMODORO:
                    if not self.is_break:
                        if self.active_task_id and self.elapsed_seconds > 0:
                            task_dict = self.app.get_task_by_id(self.active_task_id) if hasattr(self.app, "get_task_by_id") else None
                            if task_dict:
                                task_dict["time_spent_seconds"] = task_dict.get("time_spent_seconds", 0) + self.elapsed_seconds
                                if hasattr(self.app, "schedule_save"):
                                    self.app.schedule_save(tasks=True)
                        self.elapsed_seconds = 0
                        self.state = SessionState.WAITING_BREAK
                        self._stop_interval()
                        self._refresh_active_widget()
                        self._refresh_overlay_modal()
                        if hasattr(self.app, "update_header"):
                            self.app.update_header()
                        return
                else:
                    self.state = SessionState.WAITING_WORK
                    self._stop_interval()
                    self._refresh_active_widget()
                    self._refresh_overlay_modal()
                    if hasattr(self.app, "update_header"):
                        self.app.update_header()
                    return

        self._refresh_active_widget()
        self._refresh_overlay_modal()
        if hasattr(self.app, "update_header"):
            self.app.update_header()

    def _refresh_overlay_modal(self) -> None:
        from endtime.widgets.session_overlay import SessionOverlayModal
        try:
            for screen in reversed(getattr(self.app, "_screen_stack", [])):
                if isinstance(screen, SessionOverlayModal):
                    screen._on_tick()
                    break
        except Exception:
            pass

    def get_progress(self) -> Tuple[int, int, float]:
        """Return (elapsed_seconds, total_duration, progress_ratio 0.0-1.0)."""
        if self.session_type == SessionType.STOPWATCH:
            total_spent = self.elapsed_seconds
            if self.active_task_id and hasattr(self.app, "get_task_by_id"):
                task = self.app.get_task_by_id(self.active_task_id)
                if task:
                    total_spent += task.get("time_spent_seconds", 0)
            return self.elapsed_seconds, max(1, total_spent), 1.0

        total = max(1, self.total_cycle_seconds)
        remaining = max(0, self.duration_seconds)
        elapsed = max(0, total - remaining)
        ratio = min(1.0, max(0.0, elapsed / total))
        return elapsed, total, ratio

    def get_badge_text(self) -> str:
        """Get session badge for active running/paused session."""
        if self.state == SessionState.IDLE:
            return ""

        if self.session_type == SessionType.STOPWATCH:
            time_str = format_duration(self.elapsed_seconds)
            prefix = "T "
        elif self.session_type == SessionType.LONG_BREAK:
            time_str = format_duration(self.duration_seconds)
            prefix = "LB "
        elif self.session_type == SessionType.BREAK:
            time_str = format_duration(self.duration_seconds)
            prefix = "B "
        else:
            time_str = format_duration(self.duration_seconds)
            prefix = "P "

        if self.state in (SessionState.PAUSED, SessionState.WAITING_BREAK, SessionState.WAITING_WORK):
            return f"⏸ {prefix}{time_str}"
        return f"● {prefix}{time_str}"

    def get_saved_badge_text(self, task_dict: Optional[Dict[str, Any]]) -> str:
        """Get badge for a task with a saved snapshot when session is inactive."""
        if not task_dict or not task_dict.get("saved_session"):
            return ""
        saved = task_dict["saved_session"]
        stype = saved.get("type", SessionType.POMODORO)
        rem = saved.get("remaining_seconds", 0)
        elapsed = saved.get("elapsed_seconds", 0)

        if stype == SessionType.STOPWATCH:
            time_str = format_duration(elapsed)
            return f"⏸ T {time_str}"
        elif stype == SessionType.LONG_BREAK:
            time_str = format_duration(rem)
            return f"⏸ LB {time_str}"
        elif stype == SessionType.BREAK:
            time_str = format_duration(rem)
            return f"⏸ B {time_str}"
        else:
            time_str = format_duration(rem)
            return f"⏸ P {time_str}"

    def get_overlay_title(self) -> str:
        """Get stylized overlay header title string."""
        if self.session_type == SessionType.STOPWATCH:
            return "S T O P W A T C H"
        if self.session_type == SessionType.LONG_BREAK:
            return f"L O N G   B R E A K   —   C Y C L E   {self.pomodoro_round}"
        if self.session_type == SessionType.BREAK:
            return f"S H O R T   B R E A K   —   C Y C L E   {self.pomodoro_round}"
        if self.session_type == SessionType.POMODORO:
            return f"P O M O D O R O   —   C Y C L E   {self.pomodoro_round} / 4"
        return "S E S S I O N"

    def get_header_badge(self) -> str:
        """Get header bar badge string for the currently active session."""
        if self.state == SessionState.IDLE or not self.active_task_id:
            return ""

        task_display = "Unknown"
        if hasattr(self.app, "tasks_data"):
            for t in getattr(self.app, "tasks_data", []):
                if t["id"] == self.active_task_id:
                    _, task_display = parse_task(t["text"], t)
                    break

        clean_display = task_display[:24] + "…" if len(task_display) > 24 else task_display
        status_color = "#ff4444" if self.state == SessionState.RUNNING else "#777777"
        return f"[{status_color}][b]{self.get_badge_text()}[/b][/] [#aaaaaa]{clean_display}[/] | "

    def _refresh_active_widget(self) -> None:
        if self.active_task_id:
            self._refresh_widget_by_id(self.active_task_id)

    def _refresh_widget_by_id(self, task_id: str) -> None:
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

            task_dict = self.app.get_task_by_id(task_id) if hasattr(self.app, "get_task_by_id") else None
            time_spent = task_dict.get("time_spent_seconds", 0) if task_dict else 0
            if self.active_task_id == task_id:
                badge = self.get_badge_text()
            elif task_dict and task_dict.get("saved_session"):
                badge = self.get_saved_badge_text(task_dict)
            else:
                badge = ""

            for child in task_list.children:
                if isinstance(child, TodoItem) and child.task_id == task_id:
                    child.update_data_and_refresh(
                        session_badge=badge,
                        time_spent_seconds=time_spent,
                    )
                    break
        except Exception:
            pass
