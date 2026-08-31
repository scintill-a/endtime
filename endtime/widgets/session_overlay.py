"""Fullscreen session overlay modal for Endtime TUI."""
from typing import Optional
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static, Digits
from endtime.models import format_duration
from endtime.session import SessionState, SessionType


def render_ascii_progress_bar(ratio: float, width: int = 24) -> str:
    """Render a sleek ASCII progress bar."""
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    empty = width - filled
    pct = int(round(ratio * 100))
    bar = "█" * filled + "░" * empty
    return f"[#ff4444]{bar[:filled]}[/][#333333]{bar[filled:]}[/] {pct}%"


class SessionOverlayModal(ModalScreen[Optional[str]]):
    """Fullscreen minimal modal overlay to purely focus on the ticking clock and active task."""

    DEFAULT_CSS = """
    SessionOverlayModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #overlay-card {
        width: 50;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: solid #2a2a2a;
        background: #090909;
    }

    #overlay-type {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #overlay-timer {
        color: #ffffff;
        text-align: center;
        margin-bottom: 1;
        width: 100%;
    }

    #overlay-progress {
        color: #888888;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #overlay-cycles {
        color: #888888;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #overlay-task {
        color: #cccccc;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
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

    def compose(self) -> ComposeResult:
        title = self.session_type_display
        if hasattr(self.app, "session") and hasattr(self.app.session, "get_overlay_title"):
            title = self.app.session.get_overlay_title()
        with Static(id="overlay-card"):
            yield Label(title, id="overlay-type")
            yield Digits(self._get_timer_string(), id="overlay-timer")
            yield Label("", id="overlay-progress", markup=True)
            yield Label("", id="overlay-cycles", markup=True)
            yield Label(f"[b]{self.task_display[:38]}[/b]", id="overlay-task", markup=True)
            yield Label("", id="overlay-hints", markup=True)

    def on_mount(self) -> None:
        self.focus()
        self._tick_interval = self.set_interval(0.5, self._on_tick)
        self._on_tick()

    def _get_timer_string(self) -> str:
        if not hasattr(self.app, "session") or self.app.session.state == SessionState.IDLE:
            return "00:00"

        if self.app.session.session_type == SessionType.STOPWATCH:
            return format_duration(self.app.session.elapsed_seconds)
        else:
            return format_duration(self.app.session.duration_seconds)

    def _render_cycles(self) -> str:
        if not hasattr(self.app, "session"):
            return ""
        if self.app.session.session_type not in (SessionType.POMODORO, SessionType.BREAK, SessionType.LONG_BREAK):
            return ""
        current = getattr(self.app.session, "pomodoro_round", 1)
        cycle_idx = ((current - 1) % 4) + 1
        pills = []
        for i in range(1, 5):
            if i < cycle_idx:
                pills.append("[#ff4444]●[/]")
            elif i == cycle_idx:
                pills.append("[#ffffff][b]●[/b][/]")
            else:
                pills.append("[#333333]○[/]")
        return "Cycles: " + " ".join(pills)

    def _refresh_hints(self) -> None:
        try:
            if hasattr(self.app, "session"):
                if self.app.session.state == SessionState.WAITING_BREAK:
                    is_long = getattr(self.app.session, "pomodoro_round", 1) % 4 == 0
                    break_len = "15m long" if is_long else "5m"
                    self.query_one("#overlay-hints", Label).update(
                        f"[#ffffff][b]\\[enter/n] start {break_len} break[/][/]\n[#777777]\\[s] save & exit   \\[m/esc] minimize[/]"
                    )
                    return
                elif self.app.session.state == SessionState.WAITING_WORK:
                    next_cycle = getattr(self.app.session, "pomodoro_round", 1) + 1
                    self.query_one("#overlay-hints", Label).update(
                        f"[#ffffff][b]\\[enter/n] start cycle {next_cycle}[/][/]\n[#777777]\\[s] save & exit   \\[m/esc] minimize[/]"
                    )
                    return

            pause_label = "\\[p] pause" if hasattr(self.app, "session") and self.app.session.state == SessionState.RUNNING else "\\[p] resume"
            actions_line1 = [
                pause_label,
                "\\[m/esc] minimize",
                "\\[s] save",
            ]
            actions_line2 = [
                "\\[x] finish task",
                "\\[c] cancel",
            ]
            part1 = "  ".join(f"[#777777]{act}[/]" for act in actions_line1)
            part2 = "  ".join(f"[#777777]{act}[/]" for act in actions_line2)
            self.query_one("#overlay-hints", Label).update(f"{part1}\n{part2}")
        except Exception:
            pass

    def _safe_dismiss(self, result: Optional[str] = None) -> None:
        if self._tick_interval is not None:
            try:
                self._tick_interval.stop()
            except Exception:
                pass
            self._tick_interval = None
        self.dismiss(result)

    def _on_tick(self) -> None:
        if hasattr(self.app, "session"):
            if self.app.session.state == SessionState.IDLE:
                self._safe_dismiss("finished")
                return
            try:
                timer_widget = self.query_one("#overlay-timer", Digits)
                timer_widget.update(self._get_timer_string())
                if self.app.session.state in (SessionState.PAUSED, SessionState.WAITING_BREAK, SessionState.WAITING_WORK):
                    timer_widget.styles.color = "#777777"
                else:
                    timer_widget.styles.color = "#ffffff"

                if hasattr(self.app.session, "get_overlay_title"):
                    self.query_one("#overlay-type", Label).update(self.app.session.get_overlay_title())

                if hasattr(self.app.session, "get_progress"):
                    _, _, ratio = self.app.session.get_progress()
                    if self.app.session.session_type != SessionType.STOPWATCH:
                        self.query_one("#overlay-progress", Label).update(render_ascii_progress_bar(ratio))
                        self.query_one("#overlay-progress", Label).display = True
                    else:
                        self.query_one("#overlay-progress", Label).display = False

                self.query_one("#overlay-cycles", Label).update(self._render_cycles())
                self._refresh_hints()
            except Exception:
                pass

    def on_key(self, event) -> None:
        key = getattr(event, "key", "").lower()
        char = getattr(event, "character", "")

        if hasattr(self.app, "session") and self.app.session.state in (SessionState.WAITING_BREAK, SessionState.WAITING_WORK):
            if key in ("enter", "space", "n") or char in ("n", "N"):
                self.app.session.transition_next()
                self._on_tick()
                event.prevent_default()
                return
            elif key == "s" or char in ("s", "S"):
                self.app.session.stop_and_save(preserve_snapshot=True)
                self._safe_dismiss("saved")
                event.prevent_default()
                return
            elif key in ("escape", "m") or char in ("m", "M"):
                self._safe_dismiss("minimized")
                event.prevent_default()
                return

        if key in ("p", "space") or char in ("p", "P"):
            if hasattr(self.app, "session"):
                self.app.session.toggle_pause()
                self._on_tick()
            event.prevent_default()
        elif key in ("m", "escape") or char in ("m", "M"):
            self._safe_dismiss("minimized")
            event.prevent_default()
        elif key == "s" or char in ("s", "S"):
            if hasattr(self.app, "session"):
                self.app.session.stop_and_save(preserve_snapshot=True)
            self._safe_dismiss("saved")
            event.prevent_default()
        elif key == "x" or char in ("x", "X"):
            if hasattr(self.app, "session"):
                self.app.session.tick_and_save()
            self._safe_dismiss("ticked")
            event.prevent_default()
        elif key in ("c", "q") or char in ("c", "C", "q", "Q"):
            if hasattr(self.app, "session"):
                self.app.session.cancel_session()
            self._safe_dismiss("cancelled")
            event.prevent_default()
