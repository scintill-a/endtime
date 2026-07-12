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
        background: rgba(0, 0, 0, 0.90);
    }

    #overlay-card {
        width: 60;
        height: auto;
        align: center middle;
        padding: 3 4;
        border: double #ff4444;
        background: #050505;
    }

    #overlay-type {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 2;
    }

    #overlay-timer {
        color: #ffffff;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 2;
    }

    #overlay-task {
        color: #aaaaaa;
        width: 100%;
        text-align: center;
        margin-bottom: 3;
    }

    #overlay-hints {
        color: #444444;
        width: 100%;
        text-align: center;
    }
    """

    def __init__(self, task_display: str, session_type_display: str, **kwargs):
        super().__init__(**kwargs)
        self.task_display = task_display
        self.session_type_display = session_type_display
        self._tick_interval = None

    def compose(self) -> ComposeResult:
        with Static(id="overlay-card"):
            yield Label(self.session_type_display, id="overlay-type")
            yield Label(self._get_timer_string(), id="overlay-timer")
            yield Label(f"[b]{self.task_display}[/b]", id="overlay-task")
            yield Label("[p] Pause/Resume    [s] Stop & Save    [c] Cancel", id="overlay-hints")

    def on_mount(self) -> None:
        self._tick_interval = self.set_interval(0.5, self._on_tick)

    def _get_timer_string(self) -> str:
        if not hasattr(self.app, "session") or self.app.session.state == SessionState.IDLE:
            return "00:00"
        
        if self.app.session.session_type == SessionType.STOPWATCH:
            time_str = format_duration(self.app.session.elapsed_seconds)
        else:
            time_str = format_duration(self.app.session.duration_seconds)
            
        if self.app.session.state == SessionState.PAUSED:
            return f"{time_str}  (PAUSED)"
        return time_str

    def _on_tick(self) -> None:
        if hasattr(self.app, "session"):
            if self.app.session.state == SessionState.IDLE:
                self.dismiss("finished")
                return
            try:
                self.query_one("#overlay-timer", Label).update(self._get_timer_string())
            except Exception:
                pass

    def on_key(self, event) -> None:
        if event.character in ("p", "P"):
            if hasattr(self.app, "session"):
                self.app.session.toggle_pause()
                self._on_tick()
            event.prevent_default()
        elif event.character in ("s", "S"):
            if hasattr(self.app, "session"):
                self.app.session.stop_and_save()
            self.dismiss("saved")
            event.prevent_default()
        elif event.character in ("c", "C") or event.key == "escape":
            if hasattr(self.app, "session"):
                self.app.session.cancel_session()
            self.dismiss("cancelled")
            event.prevent_default()
