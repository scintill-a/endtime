"""Help and keybindings cheatsheet modal for Endtime TUI."""
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class HelpModal(ModalScreen[None]):
    """Fullscreen minimal modal overlay displaying all keybindings categorized."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #help-card {
        width: 58;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: solid #2a2a2a;
        background: #090909;
    }

    .help-title {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    .help-section-title {
        color: #ff4444;
        text-style: bold;
        width: 100%;
        margin-top: 1;
        margin-bottom: 0;
    }

    .help-row {
        width: 100%;
        layout: horizontal;
        height: 1;
    }

    .help-key {
        color: #ffffff;
        text-style: bold;
        width: 14;
        text-align: right;
        margin-right: 2;
    }

    .help-desc {
        color: #aaaaaa;
        width: 1fr;
        text-align: left;
    }

    .help-hint {
        color: #555555;
        width: 100%;
        text-align: center;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="help-card"):
            yield Label("E N D T I M E   //   C H E A T S H E E T", classes="help-title")

            sections = [
                (
                    "NAVIGATION & LIST",
                    [
                        ("j / k", "Navigate tasks down / up"),
                        ("Shift+J/K", "Reorder task within tag / reorder tag"),
                        ("gg / G", "Jump to top / jump to bottom"),
                        ("/ ", "Search & filter tasks in real-time"),
                        ("c", "Collapse / expand active category tag"),
                    ],
                ),
                (
                    "TASK MANAGEMENT",
                    [
                        ("Space", "Check / uncheck task"),
                        ("i", "Insert new task ([TAG] text @schedule)"),
                        ("e", "Edit selected task"),
                        ("d", "Delete selected task"),
                        ("f", "Toggle task focus (importance)"),
                        ("y", "Yank / copy task (or category) to clipboard"),
                        ("Shift+C", "Sweep all completed tasks"),
                    ],
                ),
                (
                    "SESSIONS & SCHEDULING",
                    [
                        ("w", "Work session (Start, Continue, or Picker)"),
                        ("@", "Schedule task / set reminder popup"),
                        ("r", "Reset task accumulated time"),
                    ],
                ),
            ]

            for section_title, bindings in sections:
                yield Label(f"── {section_title} ──", classes="help-section-title")
                for key, desc in bindings:
                    with Static(classes="help-row"):
                        yield Label(f"\\[{key}]", classes="help-key")
                        yield Label(desc, classes="help-desc")

            yield Label("\\[H / ? / esc / q] close cheatsheet", classes="help-hint")

    def on_key(self, event) -> None:
        key = getattr(event, "key", "").lower()
        char = getattr(event, "character", "")
        if key in ("escape", "question_mark", "q", "h") or char in ("H", "h", "q", "Q", "?"):
            self.dismiss()
            event.prevent_default()
