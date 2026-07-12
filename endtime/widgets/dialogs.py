"""Modal popup dialogs for Endtime working sessions and confirmations."""
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class SessionSelectDialog(ModalScreen[Optional[str]]):
    """Modal dialog for selecting a working session type."""

    def __init__(self, task_display: str):
        super().__init__()
        self.task_display = task_display

    def compose(self) -> ComposeResult:
        with Container(classes="dialog-box"):
            yield Label("START WORKING SESSION", classes="dialog-title")
            yield Label(f"Task: {self.task_display}", classes="dialog-task")
            yield Button("[1] Pomodoro (25m)", id="opt-1", classes="dialog-btn")
            yield Button("[2] Short Break (5m)", id="opt-2", classes="dialog-btn")
            yield Button("[3] Stopwatch", id="opt-3", classes="dialog-btn")
            yield Button("Cancel", id="cancel", classes="dialog-btn cancel-btn")

    def on_mount(self) -> None:
        # Focus the first option by default
        self.query_one("#opt-1").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "opt-1":
            self.dismiss("1")
        elif button_id == "opt-2":
            self.dismiss("2")
        elif button_id == "opt-3":
            self.dismiss("3")
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.character in ("1", "2", "3"):
            self.dismiss(event.character)
            event.prevent_default()
        elif event.key == "escape":
            self.dismiss(None)
            event.prevent_default()


class SessionControlDialog(ModalScreen[Optional[str]]):
    """Modal dialog for controlling an active working session."""

    def __init__(self, task_display: str, session_info: str, is_paused: bool = False):
        super().__init__()
        self.task_display = task_display
        self.session_info = session_info
        self.is_paused = is_paused

    def compose(self) -> ComposeResult:
        with Container(classes="dialog-box"):
            yield Label("ACTIVE WORKING SESSION", classes="dialog-title")
            yield Label(f"Task: {self.task_display}", classes="dialog-task")
            yield Label(f"Status: {self.session_info}", classes="dialog-status-info")
            resume_pause_lbl = "[P] Resume" if self.is_paused else "[P] Pause"
            yield Button(resume_pause_lbl, id="opt-p", classes="dialog-btn")
            yield Button("[S] Stop & Save Time", id="opt-s", classes="dialog-btn save-btn")
            yield Button("[C] Cancel Session", id="opt-c", classes="dialog-btn cancel-btn")
            yield Button("Close", id="cancel", classes="dialog-btn")

    def on_mount(self) -> None:
        self.query_one("#opt-p").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "opt-p":
            self.dismiss("p")
        elif button_id == "opt-s":
            self.dismiss("s")
        elif button_id == "opt-c":
            self.dismiss("c")
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        char = (event.character or "").lower()
        if char in ("p", "s", "c"):
            self.dismiss(char)
            event.prevent_default()
        elif event.key == "escape":
            self.dismiss(None)
            event.prevent_default()


class ConfirmDialog(ModalScreen[bool]):
    """Modal dialog for generic confirmations (e.g. deletions or sweeps)."""

    def __init__(self, title: str, message: str):
        super().__init__()
        self.title_text = title
        self.message_text = message

    def compose(self) -> ComposeResult:
        with Container(classes="dialog-box confirm-box"):
            yield Label(self.title_text, classes="dialog-title")
            yield Label(self.message_text, classes="dialog-msg")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Yes", id="confirm", classes="dialog-btn-small confirm-btn")
                yield Button("No", id="cancel", classes="dialog-btn-small")

    def on_mount(self) -> None:
        # Default to cancel/No for safety
        self.query_one("#cancel").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key in ("y", "Y", "enter"):
            self.dismiss(True)
            event.prevent_default()
        elif event.key in ("n", "N", "escape"):
            self.dismiss(False)
            event.prevent_default()
