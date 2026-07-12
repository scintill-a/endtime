"""Fullscreen session overlay modal for Endtime TUI."""
from typing import Optional
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static
from endtime.models import format_duration
from endtime.session import SessionState, SessionType


class SessionOverlayModal(ModalScreen[Optional[str]]):
    """Fullscreen minimal modal overlay covering other tasks to purely focus on the ticking clock and active task."""

    DEFAULT_CSS = """
    SessionOverlayModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.65);
    }

    #overlay-card {
        width: 42;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: solid #222222;
        background: #080808;
    }

    #overlay-type {
        color: #777777;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #overlay-timer {
        color: #ffffff;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #overlay-task {
        color: #aaaaaa;
        width: 100%;
        text-align: center;
        margin-bottom: 2;
    }

    #overlay-hints {
        color: #555555;
        width: 100%;
        text-align: center;
    }
    """

    def __init__(self, task_display: str, session_type_display: str, **kwargs):
        super().__init__(**kwargs)
        self.task_display = task_display
        self.session_type_display = session_type_display
        self._tick_interval = None
        self.selected_action: int = 0  # 0: pause, 1: save, 2: cancel

    def compose(self) -> ComposeResult:
        with Static(id="overlay-card"):
            yield Label(self.session_type_display, id="overlay-type")
            yield Label(self._get_timer_string(), id="overlay-timer")
            yield Label(f"{self.task_display[:32]}", id="overlay-task")
            yield Label("", id="overlay-hints")

    def on_mount(self) -> None:
        self._tick_interval = self.set_interval(0.5, self._on_tick)
        self._refresh_hints()

    def _get_timer_string(self) -> str:
        if not hasattr(self.app, "session") or self.app.session.state == SessionState.IDLE:
            return "00:00"
        
        if self.app.session.session_type == SessionType.STOPWATCH:
            time_str = format_duration(self.app.session.elapsed_seconds)
        else:
            time_str = format_duration(self.app.session.duration_seconds)
            
        if self.app.session.state == SessionState.PAUSED:
            return f"{time_str} (PAUSED)"
        return time_str

    def _refresh_hints(self) -> None:
        try:
            pause_label = "\\[p]ause" if hasattr(self.app, "session") and self.app.session.state == SessionState.RUNNING else "\\[p]resume"
            actions = [
                pause_label,
                "\\[s]ave",
                "\\[c/q]ancel",
            ]
            parts = []
            for i, act in enumerate(actions):
                if i == self.selected_action:
                    parts.append(f"[#ff4444]>[/][#ffffff][b]{act}[/b][/]")
                else:
                    parts.append(f"[#777777]{act}[/]")
            
            self.query_one("#overlay-hints", Label).update("  ".join(parts))
        except Exception:
            pass

    def _safe_dismiss(self, result: Optional[str] = None) -> None:
        if self._tick_interval is not None:
            try:
                self._tick_interval.stop()
            except Exception:
                pass
            self._tick_interval = None
        try:
            if getattr(self.app, "screen", None) is self:
                self.dismiss(result)
        except Exception:
            pass

    def _on_tick(self) -> None:
        if hasattr(self.app, "session"):
            if self.app.session.state == SessionState.IDLE:
                self._safe_dismiss("finished")
                return
            try:
                self.query_one("#overlay-timer", Label).update(self._get_timer_string())
                self._refresh_hints()
            except Exception:
                pass

    def _execute_selected_action(self) -> None:
        if self.selected_action == 0:
            if hasattr(self.app, "session"):
                self.app.session.toggle_pause()
                self._on_tick()
        elif self.selected_action == 1:
            if hasattr(self.app, "session"):
                self.app.session.stop_and_save()
            self._safe_dismiss("saved")
        elif self.selected_action == 2:
            if hasattr(self.app, "session"):
                self.app.session.cancel_session()
            self._safe_dismiss("cancelled")

    def on_key(self, event) -> None:
        if event.character in ("l", "j") or event.key in ("right", "down", "tab"):
            self.selected_action = (self.selected_action + 1) % 3
            self._refresh_hints()
            event.prevent_default()
        elif event.character in ("h", "k") or event.key in ("left", "up"):
            self.selected_action = (self.selected_action - 1) % 3
            self._refresh_hints()
            event.prevent_default()
        elif event.key == "enter":
            self._execute_selected_action()
            event.prevent_default()
        elif event.character in ("p", "P") or event.key == "space":
            if hasattr(self.app, "session"):
                self.app.session.toggle_pause()
                self._on_tick()
            event.prevent_default()
        elif event.character in ("s", "S"):
            if hasattr(self.app, "session"):
                self.app.session.stop_and_save()
            self._safe_dismiss("saved")
            event.prevent_default()
        elif event.character in ("c", "C", "q", "Q") or event.key == "escape":
            if hasattr(self.app, "session"):
                self.app.session.cancel_session()
            self._safe_dismiss("cancelled")
            event.prevent_default()
