"""Session picker popup modal for Endtime TUI."""
from typing import Optional
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class SessionPickerModal(ModalScreen[Optional[str]]):
    """Floating modal dialog to pick a Pomodoro, Break, or Stopwatch session."""

    DEFAULT_CSS = """
    SessionPickerModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #picker-card {
        width: 42;
        height: auto;
        background: #0a0a0a;
        border: solid #333333;
        padding: 1 2;
    }

    .modal-title {
        color: #ffffff;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .modal-subtitle {
        color: #ff4444;
        width: 100%;
        margin-bottom: 1;
    }

    .modal-option {
        color: #aaaaaa;
        margin-bottom: 1;
    }

    .modal-hint {
        color: #555555;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    def __init__(self, task_display: str, **kwargs):
        super().__init__(**kwargs)
        self.task_display = task_display

    def compose(self) -> ComposeResult:
        with Static(id="picker-card"):
            yield Label("[b]START WORKING SESSION[/b]", classes="modal-title")
            yield Label(f"Task: {self.task_display}", classes="modal-subtitle")
            yield Label("[1]  Pomodoro       25:00", classes="modal-option")
            yield Label("[2]  Short Break    05:00", classes="modal-option")
            yield Label("[3]  Stopwatch      ∞", classes="modal-option")
            yield Label("[Esc] Cancel", classes="modal-hint")

    def on_key(self, event) -> None:
        if event.character == "1":
            self.dismiss("pomodoro")
            event.prevent_default()
        elif event.character == "2":
            self.dismiss("break")
            event.prevent_default()
        elif event.character == "3":
            self.dismiss("stopwatch")
            event.prevent_default()
        elif event.key == "escape":
            self.dismiss(None)
            event.prevent_default()
