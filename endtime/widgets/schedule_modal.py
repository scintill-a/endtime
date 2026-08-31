"""Schedule picker popup modal for Endtime TUI."""
from typing import Optional
from datetime import datetime, timedelta, time
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, Static, Input
from endtime.schedule import parse_schedule_string


class ScheduleModal(ModalScreen[Optional[datetime]]):
    """Floating modal dialog to schedule a reminder or due date for a task."""

    can_focus = True

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "select_action", "Select", show=False),
        Binding("space", "select_action", "Select", show=False),
        Binding("escape", "cancel_action", "Cancel", show=False),
        Binding("q", "cancel_action", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    ScheduleModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #schedule-card {
        width: 48;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: solid #333333;
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
        color: #888888;
        width: 100%;
        height: 1;
    }

    #custom-schedule-input {
        background: #141414;
        color: #ffffff;
        border: solid #333333;
        margin-top: 1;
        display: none;
    }

    #custom-schedule-input:focus {
        border: solid #ff4444;
    }

    .modal-hint {
        color: #555555;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    def __init__(self, task_display: str, is_scheduled: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.task_display = task_display
        self.is_scheduled = is_scheduled
        self.selected_index: int = 0
        self.custom_mode = False
        self.options = [
            ("15m", "[1] In 15 minutes"),
            ("30m", "[2] In 30 minutes"),
            ("1h", "[3] In 1 hour"),
            ("evening", "[4] Today at 18:00 (Evening)"),
            ("tomorrow", "[5] Tomorrow at 09:00 (Morning)"),
            ("custom", "[6] Custom date / time..."),
        ]
        if self.is_scheduled:
            self.options.append(("clear", "[7] ↺ Clear Schedule"))

    def compose(self) -> ComposeResult:
        with Static(id="schedule-card"):
            yield Label("S C H E D U L E   R E M I N D E R", classes="modal-title")
            yield Label(f"{self.task_display[:38]}", classes="modal-subtitle")
            for i, (_, _) in enumerate(self.options):
                yield Label("", id=f"opt-{i}", classes="modal-option")
            yield Input(placeholder="e.g. 15:30, tomorrow 2pm, in 45m", id="custom-schedule-input")
            yield Label("\\[1-6] select  \\[j/k] nav  \\[enter] confirm  \\[esc] cancel", classes="modal-hint")

    def on_mount(self) -> None:
        self.focus()
        self._refresh_options()

    def _refresh_options(self) -> None:
        for i, (action, label_text) in enumerate(self.options):
            try:
                lbl = self.query_one(f"#opt-{i}", Label)
                if i == self.selected_index:
                    if action == "clear":
                        lbl.update(f"[#ff4444]>[/] [#ff4444][b]{label_text}[/b][/]")
                    else:
                        lbl.update(f"[#ff4444]>[/] [#ffffff][b]{label_text}[/b][/]")
                else:
                    if action == "clear":
                        lbl.update(f"  [#883333]{label_text}[/]")
                    else:
                        lbl.update(f"  [#888888]{label_text}[/]")
            except Exception:
                pass

    def action_cursor_down(self) -> None:
        if not self.custom_mode:
            self.selected_index = (self.selected_index + 1) % len(self.options)
            self._refresh_options()

    def action_cursor_up(self) -> None:
        if not self.custom_mode:
            self.selected_index = (self.selected_index - 1) % len(self.options)
            self._refresh_options()

    def action_select_action(self) -> None:
        if self.custom_mode:
            return
        action = self.options[self.selected_index][0]
        if action == "custom":
            self._open_custom_input()
        else:
            self._safe_dismiss(self._resolve_selection(action))

    def action_cancel_action(self) -> None:
        if self.custom_mode:
            self.custom_mode = False
            try:
                inp = self.query_one("#custom-schedule-input", Input)
                inp.display = False
            except Exception:
                pass
            self.focus()
            self._refresh_options()
        else:
            self._safe_dismiss(None)

    def _open_custom_input(self) -> None:
        self.custom_mode = True
        try:
            inp = self.query_one("#custom-schedule-input", Input)
            inp.display = True
            inp.value = ""
            inp.focus()
        except Exception:
            pass

    def _resolve_selection(self, action: str) -> Optional[datetime]:
        now = datetime.now()
        if action == "15m":
            return now + timedelta(minutes=15)
        elif action == "30m":
            return now + timedelta(minutes=30)
        elif action == "1h":
            return now + timedelta(hours=1)
        elif action == "evening":
            target_time = time(18, 0)
            target_date = now.date()
            if now.time() >= target_time:
                target_date += timedelta(days=1)
            return datetime.combine(target_date, target_time)
        elif action == "tomorrow":
            return datetime.combine(now.date() + timedelta(days=1), time(9, 0))
        elif action == "clear":
            return "CLEAR"  # Sentinel string for clearing schedule
        return None

    def _safe_dismiss(self, result: Optional[datetime] = None) -> None:
        try:
            self.dismiss(result)
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            dt = parse_schedule_string(val)
            if dt:
                self._safe_dismiss(dt)
                return
        self._safe_dismiss(None)

    def on_key(self, event) -> None:
        if self.custom_mode:
            if event.key == "escape":
                self.action_cancel_action()
                event.prevent_default()
            return

        char = event.character or event.key
        if char == "1":
            self._safe_dismiss(self._resolve_selection("15m"))
            event.prevent_default()
        elif char == "2":
            self._safe_dismiss(self._resolve_selection("30m"))
            event.prevent_default()
        elif char == "3":
            self._safe_dismiss(self._resolve_selection("1h"))
            event.prevent_default()
        elif char == "4":
            self._safe_dismiss(self._resolve_selection("evening"))
            event.prevent_default()
        elif char == "5":
            self._safe_dismiss(self._resolve_selection("tomorrow"))
            event.prevent_default()
        elif char == "6":
            self._open_custom_input()
            event.prevent_default()
        elif char in ("7", "c", "C") and self.is_scheduled:
            self._safe_dismiss("CLEAR")
            event.prevent_default()
