"""Floating reminder popup alert modal for Endtime TUI."""
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static
from endtime.session import SessionType


class ReminderModal(ModalScreen[None]):
    """Floating modal alert displayed when a scheduled task is due."""

    DEFAULT_CSS = """
    ReminderModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #reminder-card {
        width: 52;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: solid #ff4444;
        background: #0d0d0d;
    }

    .reminder-header {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .reminder-task {
        color: #ffffff;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .reminder-status {
        color: #888888;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .reminder-actions {
        color: #aaaaaa;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    def __init__(self, task_id: str, task_display: str, **kwargs):
        super().__init__(**kwargs)
        self.task_id = task_id
        self.task_display = task_display

    def compose(self) -> ComposeResult:
        with Static(id="reminder-card"):
            yield Label("⏰  T A S K   R E M I N D E R", classes="reminder-header")
            yield Label(f"\"{self.task_display[:42]}\"", classes="reminder-task")
            yield Label("SCHEDULED TIME HAS ARRIVED", classes="reminder-status")
            yield Label(
                "[#ffffff][b]\\[w][/] Start Pomodoro    [#ffffff][b]\\[1][/] Snooze 10m\n"
                "[#ffffff][b]\\[2][/] Snooze 30m       [#ffffff][b]\\[3][/] Snooze 1h\n"
                "[#ff4444][b]\\[x][/] Mark Done        [#777777]\\[enter/esc] Dismiss[/]",
                classes="reminder-actions",
                markup=True,
            )

    def on_mount(self) -> None:
        self.focus()

    def _safe_dismiss(self) -> None:
        self.dismiss()

    def on_key(self, event) -> None:
        key = getattr(event, "key", "").lower()
        char = getattr(event, "character", "")

        if key == "w" or char in ("w", "W"):
            self._safe_dismiss()
            if hasattr(self.app, "session") and hasattr(self.app, "push_screen"):
                from endtime.widgets.session_overlay import SessionOverlayModal
                self.app.session.start_session(self.task_id, SessionType.POMODORO, duration=25 * 60)
                self.app.push_screen(SessionOverlayModal(self.task_display, "P O M O D O R O"))
            event.prevent_default()
        elif key == "1" or char == "1":
            if hasattr(self.app, "scheduler"):
                self.app.scheduler.snooze_task(self.task_id, minutes=10)
            self._safe_dismiss()
            event.prevent_default()
        elif key == "2" or char == "2":
            if hasattr(self.app, "scheduler"):
                self.app.scheduler.snooze_task(self.task_id, minutes=30)
            self._safe_dismiss()
            event.prevent_default()
        elif key == "3" or char == "3":
            if hasattr(self.app, "scheduler"):
                self.app.scheduler.snooze_task(self.task_id, minutes=60)
            self._safe_dismiss()
            event.prevent_default()
        elif key == "x" or char in ("x", "X"):
            task_dict = self.app.get_task_by_id(self.task_id) if hasattr(self.app, "get_task_by_id") else None
            if task_dict:
                from datetime import datetime
                task_dict["completed"] = True
                task_dict["completed_at"] = datetime.now().isoformat()
                if hasattr(self.app, "schedule_save"):
                    self.app.schedule_save(tasks=True)
                if hasattr(self.app, "refresh_list"):
                    self.app.refresh_list(keep_index=True)
            self._safe_dismiss()
            event.prevent_default()
        elif key in ("enter", "space", "escape", "q") or char in ("q", "Q"):
            self._safe_dismiss()
            event.prevent_default()
