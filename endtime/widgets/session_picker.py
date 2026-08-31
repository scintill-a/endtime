"""Session picker popup modal for Endtime TUI."""
from typing import Optional, Dict, Any
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static
from endtime.models import format_duration


class SessionPickerModal(ModalScreen[Optional[str]]):
    """Floating modal dialog to start or continue a Pomodoro, Break, or Stopwatch session."""

    DEFAULT_CSS = """
    SessionPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #picker-card {
    width: 44;
    height: auto;
    align: center middle;
    padding: 1 2;
    border: solid #2a2a2a;
    background: #090909;
    }

    .modal-title {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .modal-subtitle {
        color: #888888;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .modal-option {
        color: #aaaaaa;
        width: 100%;
        height: 1;
    }

    .modal-hint {
        color: #555555;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    def __init__(self, task_display: str, saved_session: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(**kwargs)
        self.task_display = task_display
        self.saved_session = saved_session
        self.selected_index: int = 0
        self.options = []
        self._build_options()

    def _build_options(self) -> None:
        self.options = []
        if self.saved_session:
            stype = self.saved_session.get("type", "POMODORO")
            if stype == "STOPWATCH":
                time_str = format_duration(self.saved_session.get("elapsed_seconds", 0))
                desc = f"▶ Continue Stopwatch      ({time_str})"
            else:
                time_str = format_duration(self.saved_session.get("remaining_seconds", 0))
                round_num = self.saved_session.get("pomodoro_round", 1)
                desc = f"▶ Continue {stype.capitalize()}       ({time_str} · R{round_num})"
            self.options.append(("continue", f"[0] {desc}"))

        self.options.append(("pomodoro", "[1] ⏱ Pomodoro              25:00"))
        self.options.append(("short_break", "[2] ☕ Short Break             05:00"))
        self.options.append(("long_break", "[3] 🌴 Long Break              15:00"))
        self.options.append(("stopwatch", "[4] ⏱ Stopwatch              ∞"))

        if self.saved_session:
            self.options.append(("discard", "[d] ↺ Discard Saved Work"))

    def compose(self) -> ComposeResult:
        with Static(id="picker-card"):
            yield Label("W O R K   S E S S I O N", classes="modal-title")
            yield Label(f"{self.task_display[:34]}", classes="modal-subtitle")
            for i, (_, _) in enumerate(self.options):
                yield Label("", id=f"opt-{i}", classes="modal-option")
            yield Label("\\[j/k] nav  \\[enter] select  \\[q/esc] cancel", classes="modal-hint")

    def on_mount(self) -> None:
        self._refresh_options()

    def _refresh_options(self) -> None:
        for i, (action, label_text) in enumerate(self.options):
            try:
                lbl = self.query_one(f"#opt-{i}", Label)
                if i == self.selected_index:
                    if action == "discard":
                        lbl.update(f"[#ff4444]>[/] [#ff4444][b]{label_text}[/b][/]")
                    else:
                        lbl.update(f"[#ff4444]>[/] [#ffffff][b]{label_text}[/b][/]")
                else:
                    if action == "discard":
                        lbl.update(f"  [#883333]{label_text}[/]")
                    else:
                        lbl.update(f"  [#888888]{label_text}[/]")
            except Exception:
                pass

    def _safe_dismiss(self, result: Optional[str] = None) -> None:
        try:
            if getattr(self.app, "screen", None) is self:
                self.dismiss(result)
        except Exception:
            pass

    def on_key(self, event) -> None:
        key = getattr(event, "key", "").lower()
        char = getattr(event, "character", "")

        if key in ("j", "down") or char == "j":
            self.selected_index = (self.selected_index + 1) % len(self.options)
            self._refresh_options()
            event.prevent_default()
        elif key in ("k", "up") or char == "k":
            self.selected_index = (self.selected_index - 1) % len(self.options)
            self._refresh_options()
            event.prevent_default()
        elif key in ("enter", "space"):
            self._safe_dismiss(self.options[self.selected_index][0])
            event.prevent_default()
        elif (key in ("0", "c") or char in ("0", "c", "C")) and self.saved_session:
            self._safe_dismiss("continue")
            event.prevent_default()
        elif key == "1" or char == "1":
            self._safe_dismiss("pomodoro")
            event.prevent_default()
        elif key == "2" or char == "2":
            self._safe_dismiss("short_break")
            event.prevent_default()
        elif key == "3" or char == "3":
            self._safe_dismiss("long_break")
            event.prevent_default()
        elif key == "4" or char == "4":
            self._safe_dismiss("stopwatch")
            event.prevent_default()
        elif (key == "d" or char in ("d", "D")) and self.saved_session:
            self._safe_dismiss("discard")
            event.prevent_default()
        elif key in ("escape", "q") or char in ("q", "Q"):
            self._safe_dismiss(None)
            event.prevent_default()
