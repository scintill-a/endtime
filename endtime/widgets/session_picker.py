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
        background: rgba(0, 0, 0, 0.65);
    }

    #picker-card {
        width: 38;
        height: auto;
        background: #080808;
        border: solid #222222;
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
        color: #777777;
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

    def __init__(self, task_display: str, **kwargs):
        super().__init__(**kwargs)
        self.task_display = task_display
        self.selected_index: int = 0
        self.options = [
            ("pomodoro", "[1] Pomodoro       25:00"),
            ("break",    "[2] Short Break    05:00"),
            ("stopwatch", "[3] Stopwatch      ∞"),
        ]

    def compose(self) -> ComposeResult:
        with Static(id="picker-card"):
            yield Label("[b]START SESSION[/b]", classes="modal-title")
            yield Label(f"{self.task_display[:28]}", classes="modal-subtitle")
            for i, (_, label_text) in enumerate(self.options):
                yield Label("", id=f"opt-{i}", classes="modal-option")
            yield Label("\\[j/k] nav  \\[enter] select  \\[q/esc] cancel", classes="modal-hint")

    def on_mount(self) -> None:
        self._refresh_options()

    def _refresh_options(self) -> None:
        for i, (_, label_text) in enumerate(self.options):
            try:
                lbl = self.query_one(f"#opt-{i}", Label)
                if i == self.selected_index:
                    lbl.update(f"[#ff4444]>[/] [ffffff][b]{label_text}[/b][/]")
                else:
                    lbl.update(f"  [aaaaaa]{label_text}[/]")
            except Exception:
                pass

    def on_key(self, event) -> None:
        if event.character == "j" or event.key == "down":
            self.selected_index = (self.selected_index + 1) % len(self.options)
            self._refresh_options()
            event.prevent_default()
        elif event.character == "k" or event.key == "up":
            self.selected_index = (self.selected_index - 1) % len(self.options)
            self._refresh_options()
            event.prevent_default()
        elif event.key in ("enter", "space"):
            self.dismiss(self.options[self.selected_index][0])
            event.prevent_default()
        elif event.character == "1":
            self.dismiss("pomodoro")
            event.prevent_default()
        elif event.character == "2":
            self.dismiss("break")
            event.prevent_default()
        elif event.character == "3":
            self.dismiss("stopwatch")
            event.prevent_default()
        elif event.key == "escape" or event.character in ("q", "Q"):
            self.dismiss(None)
            event.prevent_default()
